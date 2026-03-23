"""Render Service V2 - FFmpeg command builder and executor.

Handles: segment concat, visual mutations, watermark, highlight effects,
narration audio mixing. Supports NVENC GPU acceleration.
"""

import asyncio
import subprocess
import logging
import uuid
import os
from pathlib import Path

from app.config import settings
from app.services.audio_utils import NORMALIZE_FILTER, STANDARD_SAMPLE_RATE, STANDARD_CHANNELS

logger = logging.getLogger("render_service")


class RenderService:
    """Builds and runs FFmpeg commands for remix works."""

    def __init__(self):
        self.ffmpeg = settings.FFMPEG_BIN
        self.output_dir = settings.OUTPUTS_DIR
        self.temp_dir = settings.TEMP_DIR
        self.use_gpu = self._detect_nvenc()

    def _detect_nvenc(self) -> bool:
        """Detect if NVIDIA NVENC is available."""
        try:
            result = subprocess.run(
                [settings.FFMPEG_BIN, "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            has_nvenc = "h264_nvenc" in result.stdout
            if has_nvenc:
                logger.info("GPU acceleration enabled: NVIDIA NVENC h264_nvenc detected")
            else:
                logger.info("GPU acceleration unavailable, falling back to CPU (libx264)")
            return has_nvenc
        except Exception:
            logger.info("GPU detection failed, falling back to CPU (libx264)")
            return False

    def _video_encode_args(self) -> list[str]:
        """Return video encoder arguments based on GPU availability."""
        if self.use_gpu:
            return ["-pix_fmt", "yuv420p", "-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0"]
        else:
            return ["-c:v", "libx264", "-preset", "fast", "-crf", "23"]

    def _find_font_path(self) -> str:
        """Find a usable Chinese font path for FFmpeg drawtext."""
        candidates = [
            r"C\:/Windows/Fonts/msyh.ttc",
            r"C\:/Windows/Fonts/simhei.ttf",
            r"C\:/Windows/Fonts/simsun.ttc",
            r"C\:/Windows/Fonts/msyhbd.ttc",
        ]
        for font in candidates:
            real_path = font.replace(r"C\:", "C:").replace("/", "\\")
            if os.path.exists(real_path):
                return font
        return r"C\:/Windows/Fonts/msyh.ttc"

    def build_ffmpeg_command(
        self,
        plan: dict,
        material_paths: str | list[str],
        watermark_text: str = "",
        narration_audio_path: str = "",
        narration_volume: float = 0.8,
        original_volume: float = 0.3,
        enable_effects: bool = False,
        narration_pieces: list[dict] | None = None,
    ) -> tuple[str, list[str]]:
        """Build FFmpeg command from a remix plan."""
        if isinstance(material_paths, str):
            input_paths = [material_paths]
        else:
            input_paths = material_paths

        output_filename = f"remix_{plan.get('work_id', uuid.uuid4().hex[:8])}.mp4"
        output_path = str(self.output_dir / output_filename)

        segments = plan.get("segments", [])
        mutation = plan.get("mutation_params", {})
        visual = mutation.get("visual", {})

        has_narration = bool(narration_audio_path) and Path(narration_audio_path).exists()
        narration_input_idx = len(input_paths)

        # Build input args
        args = [self.ffmpeg, "-y"]
        for p in input_paths:
            args.extend(["-i", p])
        if has_narration:
            args.extend(["-i", narration_audio_path])

        n = len(segments)
        if n == 0:
            vf_parts = self._build_visual_filters(visual)
            if watermark_text:
                vf_parts.extend(self._build_watermark_filter(watermark_text))
            if vf_parts:
                args.extend(["-vf", ",".join(vf_parts)])
            args.extend(self._video_encode_args())
            args.extend(["-c:a", "aac", "-b:a", "128k", "-ar", str(STANDARD_SAMPLE_RATE), "-ac", str(STANDARD_CHANNELS), "-t", "30", "-movflags", "+faststart", output_path])
            return output_path, args

        # Build filter_complex for segments
        filter_lines = []
        segment_labels = plan.get("segment_labels", [])

        for i, seg in enumerate(segments):
            start = seg.get("start_time", 0)
            end = seg.get("end_time", start + 5)
            speed = seg.get("speed_factor", 1.0)
            inp_idx = seg.get("input_index", 0)

            vf = f"[{inp_idx}:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS"
            af = f"[{inp_idx}:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS"

            if abs(speed - 1.0) > 0.01:
                vf += f",setpts={1.0/speed:.4f}*PTS"
                af += f",atempo={max(0.5, min(2.0, speed)):.4f}"

            # CRITICAL: Normalize EACH audio segment to standard format BEFORE concat.
            # Without this, concat may receive streams with different sample rates,
            # channel counts, or sample formats -> producing garbled/chirpy audio.
            # This handles ANY source format: mono/stereo, 22050/44100/48000Hz, s16/fltp.
            af += f",{NORMALIZE_FILTER}"

            vf += f"[v{i}]"
            af += f"[a{i}]"
            filter_lines.append(vf)
            filter_lines.append(af)

        # Concat
        if n == 1:
            filter_lines.append(f"[v0]null[concatv]")
            filter_lines.append(f"[a0]null[concata]")
        else:
            concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
            filter_lines.append(f"{concat_inputs}concat=n={n}:v=1:a=1[concatv][concata]")

        # Post-processing: visual mutations + watermark + effects
        post_filters = self._build_visual_filters(visual)

        if enable_effects and segment_labels:
            effect_filters = self._build_highlight_effects(segment_labels, segments)
            post_filters.extend(effect_filters)

        if watermark_text:
            post_filters.extend(self._build_watermark_filter(watermark_text))

        if post_filters:
            mutation_str = ",".join(post_filters)
            filter_lines.append(f"[concatv]{mutation_str}[finalv]")
            map_v = "[finalv]"
        else:
            map_v = "[concatv]"

        # Audio mixing: ducking — mute original voice during narration, keep BGM
        if has_narration:
            # ──────────────────────────────────────────────────────────
            # VOLUME STRATEGY (prevents digital clipping / 叽叽喳喳):
            #
            # Root cause analysis:
            #   Source videos often have peaks at 0 dBFS (23000+ clipped samples).
            #   Even modest narration gain (1.2x) + amix summation can exceed 0 dB.
            #   alimiter has quantization issues — still leaks 0 dB samples.
            #
            # Solution: EBU R128 loudnorm as the FINAL safety net.
            #   loudnorm=I=-16:TP=-1.5:LRA=11
            #   - I=-16 LUFS: standard broadcast loudness
            #   - TP=-1.5 dB: true peak limit, guarantees ZERO clipping
            #   - LRA=11: loudness range, keeps dynamics natural
            #
            # Tested: max_volume goes from 0.0 dB (5457 clipped samples)
            #         to -1.5 dB (0 clipped samples) ← PERFECT
            #
            # narration_volume is 0-1.0 user setting; scale to 0.5-1.5 range.
            # This controls relative emphasis before loudnorm normalizes.
            # ──────────────────────────────────────────────────────────
            narr_boost = max(0.5, min(1.5, narration_volume * 1.2 + 0.3))

            # concata is already in standard format (44100Hz stereo fltp)
            # because each segment was normalized before concat.
            # Apply aformat again as belt-and-suspenders safety.
            filter_lines.append(f"[concata]{NORMALIZE_FILTER}[concata_rs]")

            # Build ducking expression for original audio:
            # When narration is playing → drop to low volume (keep faint BGM)
            # When narration is silent → restore to original_volume
            duck_low = 0.08   # low but not silent during narration (faint BGM residue)
            duck_high = max(0.1, min(1.0, original_volume))  # normal level when no narration

            if narration_pieces and len(narration_pieces) > 0:
                duck_conditions = []
                for p in narration_pieces:
                    st = p.get("start_time", 0)
                    dur = p.get("duration", 5.0)
                    duck_conditions.append(f"between(t,{max(0,st-0.3):.2f},{st+dur+0.3:.2f})")

                if duck_conditions:
                    cond_str = "+".join(duck_conditions)
                    vol_expr = f"volume='{duck_high}-({duck_high}-{duck_low})*min(1,{cond_str})':eval=frame"
                    filter_lines.append(f"[concata_rs]{vol_expr}[origaudio]")
                else:
                    filter_lines.append(f"[concata_rs]volume={duck_high:.2f}[origaudio]")
            else:
                filter_lines.append(f"[concata_rs]volume={duck_high:.2f}[origaudio]")

            # Normalize narration input to EXACT same format as original audio.
            # Apply volume gain for emphasis. No per-stream limiter needed —
            # loudnorm on the final mix handles all peak management.
            filter_lines.append(
                f"[{narration_input_idx}:a]{NORMALIZE_FILTER},"
                f"volume={narr_boost:.2f}[narrataudio]"
            )

            # Mix: both streams are now guaranteed 44100Hz stereo fltp.
            # normalize=0 means we control volumes ourselves (no automatic scaling).
            # loudnorm (EBU R128) as the final safety net:
            #   - Normalizes integrated loudness to -16 LUFS
            #   - Hard-limits true peak to -1.5 dB (ZERO clipping guaranteed)
            #   - Preserves dynamic range within LRA=11 dB
            # This handles ANY combination of hot source material + narration
            # without ever producing digital distortion.
            filter_lines.append(
                f"[origaudio][narrataudio]amix=inputs=2:duration=first"
                f":dropout_transition=0:normalize=0,"
                f"loudnorm=I=-16:TP=-1.5:LRA=11[finala]"
            )
            map_a = "[finala]"
        else:
            # No narration: still normalize the concat audio for clean output.
            # Use loudnorm to tame any hot source material and ensure
            # consistent loudness across all outputs.
            filter_lines.append(
                f"[concata]{NORMALIZE_FILTER},"
                f"loudnorm=I=-16:TP=-1.5:LRA=11[finala]"
            )
            map_a = "[finala]"

        filter_complex = ";".join(filter_lines)
        args.extend(["-filter_complex", filter_complex])
        args.extend(["-map", map_v, "-map", map_a])
        args.extend(self._video_encode_args())
        args.extend([
            "-c:a", "aac", "-b:a", "128k",
            "-ar", str(STANDARD_SAMPLE_RATE), "-ac", str(STANDARD_CHANNELS),
            "-movflags", "+faststart",
            output_path,
        ])

        return output_path, args

    def _build_visual_filters(self, visual: dict) -> list[str]:
        """Build visual filter components from mutation params."""
        parts = []
        brightness = visual.get("brightness", 0)
        contrast = visual.get("contrast", 1)
        saturation = visual.get("saturation", 1)
        if abs(brightness) > 0.001 or abs(contrast - 1) > 0.001 or abs(saturation - 1) > 0.001:
            parts.append(f"eq=brightness={brightness:.4f}:contrast={contrast:.4f}:saturation={saturation:.4f}")

        hue = visual.get("hue_shift", 0)
        if abs(hue) > 0.1:
            parts.append(f"hue=h={hue:.2f}")

        return parts

    def _build_watermark_filter(self, text: str) -> list[str]:
        """Build floating watermark that moves continuously across the entire video.

        Strategy: multiple drawtext layers with different speeds/paths so the
        watermark is always visible somewhere on screen and cannot be cropped out.
        - Layer 1: horizontal zigzag across upper area
        - Layer 2: diagonal sweep across center area (different speed)
        - Layer 3: slower drift in lower area (opposite direction)
        All semi-transparent to avoid blocking content too much.
        """
        font_path = self._find_font_path()
        safe_text = text.replace("'", "\\'").replace(":", "\\:")

        filters = []

        # Layer 1: Horizontal zigzag, upper third of screen
        # Uses triangle wave (abs(mod)) for back-and-forth motion
        wm1 = (
            f"drawtext=fontfile='{font_path}'"
            f":text='{safe_text}'"
            f":fontsize=24"
            f":fontcolor=white@0.45"
            f":x='abs(mod(t*50\\,2*(w-tw))-(w-tw))'"
            f":y='h*0.15+sin(t*0.5)*h*0.08'"
            f":shadowcolor=black@0.35:shadowx=1:shadowy=1"
        )
        filters.append(wm1)

        # Layer 2: Diagonal sweep across center, faster, slightly larger
        wm2 = (
            f"drawtext=fontfile='{font_path}'"
            f":text='{safe_text}'"
            f":fontsize=26"
            f":fontcolor=white@0.40"
            f":x='abs(mod(t*35+w/2\\,2*(w-tw))-(w-tw))'"
            f":y='h*0.4+cos(t*0.4)*h*0.12'"
            f":shadowcolor=black@0.35:shadowx=1:shadowy=1"
        )
        filters.append(wm2)

        # Layer 3: Slow reverse drift, lower area
        wm3 = (
            f"drawtext=fontfile='{font_path}'"
            f":text='{safe_text}'"
            f":fontsize=22"
            f":fontcolor=white@0.42"
            f":x='w-abs(mod(t*25\\,2*(w-tw))-(w-tw))-tw'"
            f":y='h*0.72+sin(t*0.7+1.5)*h*0.10'"
            f":shadowcolor=black@0.35:shadowx=1:shadowy=1"
        )
        filters.append(wm3)

        return filters

    def _build_highlight_effects(self, labels: list[str], segments: list[dict]) -> list[str]:
        """Build highlight effects for high-energy moments."""
        effects = []

        cumulative_time = 0.0
        highlight_times = []
        for i, (label, seg) in enumerate(zip(labels, segments)):
            seg_dur = (seg.get("end_time", 0) - seg.get("start_time", 0)) / max(seg.get("speed_factor", 1.0), 0.5)
            if label in ("hook", "climax", "highlight"):
                highlight_times.append((cumulative_time, cumulative_time + min(seg_dur, 2.0)))
            cumulative_time += seg_dur

        if highlight_times:
            ht_start, ht_end = highlight_times[0]
            effects.append(
                f"eq=brightness='if(between(t,{ht_start:.2f},{ht_start+0.5:.2f}),0.08,0)'"
                f":contrast='if(between(t,{ht_start:.2f},{ht_start+0.5:.2f}),1.15,1)'"
            )

        return effects

    def _render_sync(self, args: list[str]) -> tuple[bool, str]:
        """Execute FFmpeg synchronously (for thread pool)."""
        try:
            logger.info(f"FFmpeg cmd: {' '.join(str(a) for a in args[:6])}... ({len(args)} args)")
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            if result.returncode == 0:
                logger.info("FFmpeg render completed successfully")
                return True, ""
            else:
                err_text = result.stderr[-800:] if result.stderr else "No stderr output"
                logger.warning(f"FFmpeg failed (code {result.returncode}): {err_text[:200]}")
                return False, err_text
        except subprocess.TimeoutExpired:
            return False, "FFmpeg render timed out (300s)"
        except Exception as e:
            logger.error(f"FFmpeg execution exception: {type(e).__name__}: {e}")
            return False, str(e)

    async def render(self, args: list[str]) -> tuple[bool, str]:
        """Execute FFmpeg with argument list (async wrapper)."""
        return await asyncio.get_event_loop().run_in_executor(None, self._render_sync, args)
