"""Task Runner V2 - Orchestrates the full remix pipeline.

V2: Integrates narration (LLM + TTS), watermark, and highlight effects.
Pipeline: plan generation -> [narration generation] -> rendering -> review -> status update
"""

import asyncio
import subprocess
import logging
import json
from datetime import datetime
from pathlib import Path
from sqlalchemy import select, update

from app.database import async_session
from app.models.material import Material, MaterialSegment
from app.models.remix import RemixTask, RemixTemplate
from app.models.work import RemixWork, RenderJob
from app.models.bgm import BGMTrack
from app.models.review import ReviewResult
from app.models.bundle import MaterialBundle
from app.services.remix_engine import RemixEngine
from app.services.render_service import RenderService
from app.services.narration_service import NarrationService
from app.services.review_engine import ReviewEngine
from app.config import settings
from app.utils import beijing_now

logger = logging.getLogger("task_runner")
logging.basicConfig(level=logging.INFO)

import threading

_running_tasks: dict[str, threading.Thread] = {}


def get_running_task_ids() -> list[str]:
    return [tid for tid, t in _running_tasks.items() if t.is_alive()]


def _probe_duration_sync(file_path: str) -> float:
    """Use ffprobe (sync) to get actual video duration."""
    try:
        cmd = [
            settings.FFPROBE_BIN, "-v", "quiet", "-print_format", "json",
            "-show_format", file_path
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
        )
        if result.returncode != 0:
            logger.warning(f"ffprobe failed for {file_path}: {result.stderr[:200]}")
            return 0.0
        data = json.loads(result.stdout)
        dur = float(data.get("format", {}).get("duration", 0))
        logger.info(f"ffprobe duration for {file_path}: {dur}s")
        return dur
    except Exception as e:
        logger.warning(f"ffprobe exception for {file_path}: {type(e).__name__}: {e}")
        return 0.0


async def _probe_duration(file_path: str) -> float:
    """Async wrapper - runs sync probe in thread pool."""
    return await asyncio.get_event_loop().run_in_executor(None, _probe_duration_sync, file_path)


async def auto_segment_material(material_id: str):
    """Auto-generate segments for a material if none exist."""
    async with async_session() as db:
        result = await db.execute(select(Material).where(Material.id == material_id))
        material = result.scalar_one_or_none()
        if not material:
            return

        seg_result = await db.execute(
            select(MaterialSegment).where(MaterialSegment.material_id == material_id).limit(1)
        )
        if seg_result.scalar_one_or_none():
            if material.duration <= 0:
                probed = await _probe_duration(material.file_path)
                if probed > 0:
                    material.duration = probed
                    from sqlalchemy import delete
                    await db.execute(
                        delete(MaterialSegment).where(MaterialSegment.material_id == material_id)
                    )
                    await db.commit()
                    logger.info(f"Cleared stale segments for material {material_id}, re-probed duration={probed}s")
                else:
                    return
            else:
                return

        duration = material.duration
        if duration <= 0:
            probed = await _probe_duration(material.file_path)
            if probed > 0:
                duration = probed
                material.duration = probed
            else:
                duration = 10.0

        seg_len = 5.0
        segments = []
        t = 0.0
        idx = 0
        while t < duration:
            end = min(t + seg_len, duration)
            if end - t < 1.0:
                break
            labels = ["hook", "climax", "body", "body", "transition", "body", "ending"]
            label = labels[idx % len(labels)]
            seg = MaterialSegment(
                material_id=material_id,
                segment_index=idx,
                start_time=round(t, 3),
                end_time=round(end, 3),
                duration=round(end - t, 3),
                label=label,
                score=0.5 + (0.3 if label in ("hook", "climax") else 0.0),
            )
            segments.append(seg)
            t = end
            idx += 1

        for seg in segments:
            db.add(seg)
        await db.commit()
        logger.info(f"Auto-segmented material {material_id}: {len(segments)} segments (duration={duration}s)")


def _run_task_in_thread(task_id: str):
    """Run the task loop in a new asyncio event loop in a separate thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_task_loop(task_id))
    except Exception as e:
        logger.error(f"Task {task_id} thread crashed: {type(e).__name__}: {e}", exc_info=True)
    finally:
        loop.close()
        _running_tasks.pop(task_id, None)
        logger.info(f"Task {task_id} thread finished")


async def start_task_processing(task_id: str):
    """Entry point: schedule a task for background processing."""
    if task_id in _running_tasks and _running_tasks[task_id].is_alive():
        logger.warning(f"Task {task_id} is already running")
        return

    t = threading.Thread(target=_run_task_in_thread, args=(task_id,), daemon=True)
    _running_tasks[task_id] = t
    t.start()
    logger.info(f"Task {task_id} scheduled for background processing")


async def stop_task_processing(task_id: str):
    """Stop a running background task."""
    _running_tasks.pop(task_id, None)
    async with async_session() as db:
        result = await db.execute(select(RemixTask).where(RemixTask.id == task_id))
        task = result.scalar_one_or_none()
        if task and task.status == "running":
            task.status = "paused"
            await db.commit()
            logger.info(f"Task {task_id} set to paused")


async def _run_task_loop(task_id: str):
    """Main loop: keep producing works until target_count reached or paused."""
    render_service = RenderService()
    narration_service = NarrationService()
    review_engine = ReviewEngine()

    while True:
      try:
        # Phase 1: Load task state
        material_ids_to_load = []
        task_watermark = ""
        task_narration_enabled = False
        task_narration_volume = 0.8
        task_original_volume = 0.3
        task_effects_enabled = False
        task_narration_ratio = 30.0
        task_edge_voice = "zh-CN-XiaoxiaoNeural"
        task_episode_batch = None

        async with async_session() as db:
            result = await db.execute(select(RemixTask).where(RemixTask.id == task_id))
            task = result.scalar_one_or_none()
            if not task:
                logger.error(f"Task {task_id} not found, stopping")
                return
            if task.status != "running":
                logger.info(f"Task {task_id} status is '{task.status}', stopping loop")
                return
            if task.completed_count >= task.target_count:
                task.status = "completed"
                task.finished_at = beijing_now()
                await db.commit()
                logger.info(f"Task {task_id} completed: {task.completed_count}/{task.target_count}")
                return

            max_failures = task.target_count * 3
            if task.failed_count >= max_failures:
                task.status = "error"
                task.finished_at = beijing_now()
                await db.commit()
                logger.error(f"Task {task_id} stopped: too many failures ({task.failed_count})")
                return

            # Read V2/V3 settings
            task_watermark = task.watermark_text or ""
            task_narration_enabled = task.narration_enabled
            task_narration_volume = task.narration_volume
            task_original_volume = task.original_volume
            task_effects_enabled = task.effects_enabled
            task_narration_ratio = getattr(task, "narration_ratio", 30.0) or 30.0
            task_edge_voice = getattr(task, "edge_voice", "zh-CN-XiaoxiaoNeural") or "zh-CN-XiaoxiaoNeural"
            task_episode_batch = getattr(task, "episode_batch", None)

            if task.bundle_id:
                bundle_result = await db.execute(
                    select(MaterialBundle).where(MaterialBundle.id == task.bundle_id)
                )
                bundle = bundle_result.scalar_one_or_none()
                if bundle and bundle.material_ids:
                    all_ids = list(bundle.material_ids)
                    # Filter by episode_batch if specified
                    # batch format: "0_2" = episodes 1-3 (start=0, end=2, inclusive)
                    if task_episode_batch and "_" in task_episode_batch:
                        try:
                            parts = task_episode_batch.split("_")
                            batch_start = int(parts[0])
                            batch_end = int(parts[1])
                            material_ids_to_load = all_ids[batch_start:batch_end + 1]
                            logger.info(f"Task {task_id}: episode batch {task_episode_batch} -> material_ids {material_ids_to_load}")
                        except (ValueError, IndexError):
                            logger.warning(f"Task {task_id}: invalid episode_batch '{task_episode_batch}', using all")
                            material_ids_to_load = all_ids
                    else:
                        material_ids_to_load = all_ids
                elif task.material_id:
                    material_ids_to_load = [task.material_id]
            elif task.material_id:
                material_ids_to_load = [task.material_id]

            task_target_count = task.target_count
            task_completed_count = task.completed_count
            task_template_id = task.template_id
            task_config_json = task.config_json

        if not material_ids_to_load:
            async with async_session() as db:
                result = await db.execute(select(RemixTask).where(RemixTask.id == task_id))
                task = result.scalar_one_or_none()
                if task:
                    task.status = "error"
                    await db.commit()
            logger.error(f"Task {task_id}: no materials to process")
            return

        # Phase 2: Auto-segment
        for mid in material_ids_to_load:
            await auto_segment_material(mid)

        # Phase 3: Load segments and generate plans
        async with async_session() as db:
            mat_result = await db.execute(
                select(Material).where(Material.id.in_(material_ids_to_load))
            )
            materials_list = mat_result.scalars().all()
            if not materials_list:
                result = await db.execute(select(RemixTask).where(RemixTask.id == task_id))
                t = result.scalar_one_or_none()
                if t:
                    t.status = "error"
                    await db.commit()
                logger.error(f"Task {task_id}: materials not found")
                return

            materials_map = {m.id: m for m in materials_list}

            seg_result = await db.execute(
                select(MaterialSegment)
                .where(MaterialSegment.material_id.in_(material_ids_to_load))
                .order_by(MaterialSegment.material_id, MaterialSegment.segment_index)
            )
            segments = [
                {
                    "id": s.id,
                    "material_id": s.material_id,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration": s.duration,
                    "label": s.label,
                    "score": s.score,
                }
                for s in seg_result.scalars().all()
            ]

            if not segments:
                result2 = await db.execute(select(RemixTask).where(RemixTask.id == task_id))
                t = result2.scalar_one_or_none()
                if t:
                    t.status = "error"
                    await db.commit()
                logger.error(f"Task {task_id}: no segments available")
                return

            logger.info(f"Task {task_id}: loaded {len(segments)} segments from {len(materials_list)} material(s)")

            config = task_config_json or {}
            if task_template_id:
                tmpl_result = await db.execute(
                    select(RemixTemplate).where(RemixTemplate.id == task_template_id)
                )
                tmpl = tmpl_result.scalar_one_or_none()
                if tmpl:
                    config.setdefault("duration_range_min", tmpl.duration_range_min)
                    config.setdefault("duration_range_max", tmpl.duration_range_max)
                    config.setdefault("hook_strategy", tmpl.hook_strategy)

            bgm_result = await db.execute(select(BGMTrack).limit(20))
            bgm_ids = [b.id for b in bgm_result.scalars().all()] or None

            fp_result = await db.execute(
                select(RemixWork.fingerprint).where(
                    RemixWork.task_id == task_id,
                    RemixWork.fingerprint.isnot(None),
                )
            )
            existing_fps = {r[0] for r in fp_result.all()}

            remaining = task_target_count - task_completed_count
            batch_size = min(remaining, 5)
            engine = RemixEngine(config)
            plans = engine.generate_plans(
                segments=segments,
                count=batch_size,
                bgm_ids=bgm_ids,
                existing_fingerprints=existing_fps,
            )
            logger.info(f"Task {task_id}: generated {len(plans)} plans (batch)")

        # Process each plan
        for plan in plans:
            async with async_session() as db:
                result = await db.execute(select(RemixTask).where(RemixTask.id == task_id))
                task = result.scalar_one_or_none()
                if not task or task.status != "running":
                    return

                work_index = task.completed_count + task.failed_count + 1

                work = RemixWork(
                    task_id=task_id,
                    work_index=work_index,
                    title=f"混剪作品 #{work_index}",
                    segments_json={
                        "segments": [
                            {
                                "segment_id": s.segment_id,
                                "material_id": s.material_id,
                                "start_time": s.start_time,
                                "end_time": s.end_time,
                                "speed_factor": s.speed_factor,
                                "label": s.label,
                            }
                            for s in plan.segments
                        ]
                    },
                    bgm_id=plan.bgm_id,
                    hook_type=plan.hook_type,
                    transition_style=plan.transition_style,
                    text_overlays_json=plan.text_overlays,
                    mutation_params_json=plan.mutation_params,
                    status="rendering",
                    fingerprint=plan.fingerprint,
                )
                db.add(work)
                await db.flush()

                # Build input paths
                plan_segment_material_ids = set()
                for s in plan.segments:
                    plan_segment_material_ids.add(s.material_id)

                input_material_ids = sorted(plan_segment_material_ids)
                material_input_map = {mid: idx for idx, mid in enumerate(input_material_ids)}
                input_paths = []
                for mid in input_material_ids:
                    if mid in materials_map:
                        input_paths.append(materials_map[mid].file_path)
                    else:
                        mr = await db.execute(select(Material).where(Material.id == mid))
                        m = mr.scalar_one_or_none()
                        input_paths.append(m.file_path if m else "")

                # Segment labels for effects
                segment_labels = [s.label for s in plan.segments]

                plan_dict = {
                    "work_id": work.id,
                    "segments": [
                        {
                            "start_time": s.start_time,
                            "end_time": s.end_time,
                            "speed_factor": s.speed_factor,
                            "input_index": material_input_map.get(s.material_id, 0),
                        }
                        for s in plan.segments
                    ],
                    "segment_labels": segment_labels,
                    "mutation_params": plan.mutation_params,
                    "bgm_path": None,
                }

                render_job = RenderJob(
                    work_id=work.id,
                    ffmpeg_command="(building...)",
                    status="running",
                    started_at=beijing_now(),
                )
                db.add(render_job)
                await db.commit()
                work_id = work.id
                render_job_id = render_job.id
                logger.info(f"Task {task_id}: preparing work #{work_index}...")

            # Phase 4: Generate narration if enabled (OUTSIDE db session)
            # V3: interspersed narration with voice cloning
            narration_audio_path = ""
            narration_piece_info = []
            if task_narration_enabled:
                try:
                    segment_info = [
                        {
                            "label": s.label,
                            "start_time": s.start_time,
                            "end_time": s.end_time,
                        }
                        for s in plan.segments
                    ]

                    # Step 4a: Generate interspersed narration pieces via LLM
                    pieces = await narration_service.generate_interspersed_script(
                        segment_info=segment_info,
                        hook_type=plan.hook_type,
                        total_duration=plan.total_duration,
                        narration_ratio=task_narration_ratio,
                        narration_hint=plan.narration_hint,
                    )

                    if pieces:
                        logger.info(f"Task {task_id}: narration {len(pieces)} pieces, ratio={task_narration_ratio}%, voice={task_edge_voice}")

                        # Step 4b: Synthesize using Edge TTS
                        audio_path, synth_pieces = await narration_service.synthesize_interspersed_tts(
                            pieces=pieces,
                            total_duration=plan.total_duration,
                            work_id=work_id,
                            edge_voice=task_edge_voice,
                        )
                        if audio_path:
                            narration_audio_path = audio_path
                            narration_piece_info = synth_pieces  # [{start_time, duration, path}, ...]
                            logger.info(f"Task {task_id}: narration audio ready: {audio_path}")
                except Exception as e:
                    logger.warning(f"Task {task_id}: narration generation failed: {e}")
                    # Continue without narration - not a fatal error

            # Phase 5: Build FFmpeg command and render
            output_path, ffmpeg_cmd = render_service.build_ffmpeg_command(
                plan_dict,
                input_paths,
                watermark_text=task_watermark,
                narration_audio_path=narration_audio_path,
                narration_volume=task_narration_volume,
                original_volume=task_original_volume,
                enable_effects=task_effects_enabled,
                narration_pieces=narration_piece_info,
            )

            # Update render job with actual command
            async with async_session() as db:
                result = await db.execute(select(RenderJob).where(RenderJob.id == render_job_id))
                rj = result.scalar_one_or_none()
                if rj:
                    rj.ffmpeg_command = " ".join(str(a) for a in ffmpeg_cmd)[:2000]
                    await db.commit()

            logger.info(f"Task {task_id}: rendering work #{work_index}...")
            success, error_msg = await render_service.render(ffmpeg_cmd)

            # Phase 6: Update results
            async with async_session() as db:
                result = await db.execute(select(RenderJob).where(RenderJob.id == render_job_id))
                render_job = result.scalar_one()
                result2 = await db.execute(select(RemixWork).where(RemixWork.id == work_id))
                work = result2.scalar_one()
                result3 = await db.execute(select(RemixTask).where(RemixTask.id == task_id))
                task = result3.scalar_one()

                if success and Path(output_path).exists():
                    render_job.status = "completed"
                    render_job.progress = 100
                    render_job.finished_at = beijing_now()

                    file_size = Path(output_path).stat().st_size
                    work.output_path = output_path
                    work.file_size = file_size
                    work.status = "reviewing"

                    review_result = await review_engine.review_work(
                        output_path, plan.mutation_params
                    )
                    review = ReviewResult(
                        work_id=work.id,
                        visual_check_passed=review_result["visual_check_passed"],
                        audio_check_passed=review_result["audio_check_passed"],
                        metadata_check_passed=review_result["metadata_check_passed"],
                        dedup_check_passed=review_result["dedup_check_passed"],
                        compliance_check_passed=review_result["compliance_check_passed"],
                        overall_passed=review_result["overall_passed"],
                        similarity_score=review_result.get("similarity_score", 0),
                        issues_json=review_result.get("issues", []),
                    )
                    db.add(review)

                    if review_result["overall_passed"]:
                        work.status = "approved"
                        work.review_passed = True
                        task.completed_count += 1
                        logger.info(f"Task {task_id}: work #{work_index} APPROVED ({task.completed_count}/{task.target_count})")
                    else:
                        work.status = "rejected"
                        work.review_passed = False
                        task.failed_count += 1
                        logger.info(f"Task {task_id}: work #{work_index} REJECTED: {review_result.get('issues', [])}")
                else:
                    render_job.status = "failed"
                    render_job.error_message = error_msg[:500] if error_msg else "Unknown render error"
                    render_job.finished_at = beijing_now()
                    work.status = "rejected"
                    work.error_message = error_msg[:500] if error_msg else "Render failed"
                    task.failed_count += 1
                    logger.warning(f"Task {task_id}: work #{work_index} RENDER FAILED: {error_msg[:200] if error_msg else '?'}")

                if task.completed_count >= task.target_count:
                    task.status = "completed"
                    task.finished_at = beijing_now()

                await db.commit()

        await asyncio.sleep(0.5)

      except Exception as e:
        logger.error(f"Task {task_id} loop error: {type(e).__name__}: {e}", exc_info=True)
        try:
            async with async_session() as db:
                result = await db.execute(select(RemixTask).where(RemixTask.id == task_id))
                task = result.scalar_one_or_none()
                if task:
                    task.status = "error"
                    task.finished_at = beijing_now()
                    await db.commit()
        except Exception:
            pass
        return
