"""Narration Service - Interspersed narration with Edge TTS.

Pipeline:
1. User sets narration_ratio (e.g. 30% = 30% of video has narration)
2. LLM generates SEGMENTED narration (multiple short pieces at story beats)
3. Edge TTS synthesizes each piece using selected voice
4. Pieces are combined with silence padding into a single timeline-aligned audio track
5. Render service mixes this track with the original audio
"""

import asyncio
import json
import logging
import os
import subprocess
import uuid
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger("narration_service")


def _synthesize_edge_sync(text: str, voice: str, output_path: str) -> bool:
    """Synthesize using Edge TTS."""
    try:
        import edge_tts
        import asyncio

        async def _do():
            comm = edge_tts.Communicate(text=text, voice=voice)
            await comm.save(output_path)

        asyncio.run(_do())
        return Path(output_path).exists() and Path(output_path).stat().st_size > 100
    except Exception as e:
        logger.error(f"Edge TTS error: {type(e).__name__}: {e}")
        return False


class NarrationService:
    """Generate interspersed narration: LLM scripting + voice-cloned TTS."""

    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = settings.DEEPSEEK_BASE_URL
        self.model = settings.DEEPSEEK_MODEL
        self.output_dir = settings.NARRATION_DIR

    async def generate_interspersed_script(
        self,
        segment_info: list[dict],
        hook_type: str,
        total_duration: float,
        narration_ratio: float = 30.0,
        narration_hint: str = "",
    ) -> list[dict]:
        """Generate segmented narration script via DeepSeek LLM.

        Returns a list of narration pieces:
        [
            {"start_time": 0.0, "text": "旁白文本..."},
            {"start_time": 15.5, "text": "旁白文本..."},
            ...
        ]
        """
        ratio = max(5.0, min(80.0, narration_ratio)) / 100.0
        narration_total_sec = total_duration * ratio
        # ~3 chars/sec for natural Chinese narration pacing
        target_chars = int(narration_total_sec * 3)
        # Split into 3-6 pieces depending on video length
        piece_count = max(2, min(6, int(total_duration / 10)))

        if not self.api_key:
            logger.warning("No DeepSeek API key, using fallback interspersed narration")
            return self._fallback_interspersed(segment_info, total_duration, piece_count, target_chars)

        # Build segment timeline description
        seg_desc = []
        cum_time = 0.0
        for i, seg in enumerate(segment_info):
            dur = seg.get("end_time", 0) - seg.get("start_time", 0)
            label = seg.get("label", "body")
            seg_desc.append(f"[{cum_time:.1f}s-{cum_time+dur:.1f}s] {label}")
            cum_time += dur

        timeline_text = "\n".join(seg_desc)

        prompt = f"""你是一个短视频旁白文案写手，专门为短剧二创混剪视频撰写"穿插式"旁白解说词。

视频信息：
- 钩子类型: {hook_type}
- 总时长: {total_duration:.0f}秒
- 旁白占比: {narration_ratio:.0f}% (旁白总字数约{target_chars}字)
- 片段时间线:
{timeline_text}

你需要输出{piece_count}段旁白，每段对应视频的不同位置。旁白不是连续的，中间有留白让观众听原声。

要求：
1. 输出严格的JSON数组格式，每个元素包含 start_time (秒) 和 text (旁白文本)
2. 第一段旁白从0-3秒开始(开场钩子)
3. 最后一段旁白在结尾前5-8秒(引导关注)
4. 中间的旁白放在剧情转折点、高能时刻、情感爆发处
5. 每段旁白10-40个字，像抖音解说一样自然口语化
6. 语气要吸引人，讲故事风格，不是念台词
7. 不同段之间要有剧情推进感，不重复
8. 总字数控制在{target_chars}字左右

只输出JSON数组，不要其他内容。示例格式：
[
  {{"start_time": 0, "text": "你绝对想不到，接下来会发生什么"}},
  {{"start_time": 18, "text": "就在这时候，事情的走向彻底变了"}},
  {{"start_time": 38, "text": "看到这里，你是不是也被感动了？点个关注"}}
]"""

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "你是专业的短视频旁白文案写手。你的输出必须是合法的JSON数组。"},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.8,
                        "max_tokens": 1500,
                    },
                )
                response.raise_for_status()
                data = response.json()
                raw = data["choices"][0]["message"]["content"].strip()

                # Parse JSON - handle markdown code blocks
                if "```" in raw:
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                    raw = raw.strip()

                pieces = json.loads(raw)
                if not isinstance(pieces, list) or len(pieces) == 0:
                    raise ValueError("LLM returned empty or non-list")

                # Validate and clean
                clean = []
                for p in pieces:
                    if isinstance(p, dict) and "text" in p:
                        clean.append({
                            "start_time": float(p.get("start_time", 0)),
                            "text": str(p["text"]).strip(),
                        })
                clean.sort(key=lambda x: x["start_time"])

                total_chars = sum(len(p["text"]) for p in clean)
                logger.info(f"LLM interspersed narration: {len(clean)} pieces, {total_chars} chars")
                return clean

        except Exception as e:
            logger.error(f"DeepSeek interspersed narration error: {type(e).__name__}: {e}")
            return self._fallback_interspersed(segment_info, total_duration, piece_count, target_chars)

    def _fallback_interspersed(
        self,
        segment_info: list[dict],
        total_duration: float,
        piece_count: int,
        target_chars: int,
    ) -> list[dict]:
        """Fallback when LLM is unavailable."""
        import random

        openers = [
            "你绝对想不到，接下来会发生什么",
            "注意看，这个男人叫小帅",
            "接下来的剧情，让所有人都沉默了",
            "如果是你，你会怎么选",
        ]
        middles = [
            "就在这时候，事情急转直下",
            "没有人想到，真相竟然是这样的",
            "矛盾彻底爆发了，谁也无法置身事外",
            "命运的齿轮开始转动，一切都变了",
            "看到这里，很多人都忍不住红了眼眶",
        ]
        closers = [
            "看到这里你是不是也被感动了？点个关注不迷路",
            "想知道后面发生了什么？关注我，下集更精彩",
            "这就是真正打动人心的故事，你觉得呢",
            "如果你也喜欢这样的故事，给个赞吧",
        ]

        pieces = []
        pieces.append({"start_time": 0.0, "text": random.choice(openers)})

        if piece_count > 2:
            interval = total_duration / (piece_count - 1)
            for i in range(1, piece_count - 1):
                t = interval * i
                pieces.append({"start_time": round(t, 1), "text": random.choice(middles)})

        pieces.append({
            "start_time": round(max(total_duration - 8, total_duration * 0.8), 1),
            "text": random.choice(closers),
        })

        return pieces

    async def synthesize_interspersed_tts(
        self,
        pieces: list[dict],
        total_duration: float,
        work_id: str,
        edge_voice: str = "zh-CN-XiaoxiaoNeural",
    ) -> tuple[str | None, list[dict]]:
        """Synthesize interspersed narration pieces into a single timeline-aligned audio track.

        Uses Edge TTS (Microsoft Edge online voice synthesis).
        1. Synthesize each piece to a separate WAV
        2. Combine with silence padding to align with video timestamps
        3. Return (path_to_combined_wav, pieces_with_durations)
        """
        if not pieces:
            return None, []

        piece_wavs = []
        loop = asyncio.get_event_loop()

        for i, piece in enumerate(pieces):
            text = piece["text"]
            piece_filename = f"piece_{work_id}_{i}.wav"
            piece_path = str(self.output_dir / piece_filename)

            logger.info(f"[TTS] Piece {i}: Edge TTS, voice={edge_voice}, text={text[:30]}...")
            success = await loop.run_in_executor(
                None,
                _synthesize_edge_sync,
                text,
                edge_voice,
                piece_path,
            )

            if success and Path(piece_path).exists():
                piece_wavs.append({
                    "start_time": piece["start_time"],
                    "path": piece_path,
                    "duration": await self.get_audio_duration(piece_path),
                })
                logger.info(f"[TTS] Piece {i}: Edge TTS OK")
            else:
                logger.error(f"[TTS] Piece {i}: Edge TTS failed!")

        if not piece_wavs:
            logger.warning("No narration pieces synthesized successfully")
            return None, []

        combined_path = str(self.output_dir / f"narration_{work_id}.wav")
        success = await loop.run_in_executor(
            None, self._combine_pieces_sync, piece_wavs, total_duration, combined_path
        )

        if success and Path(combined_path).exists():
            size = Path(combined_path).stat().st_size
            logger.info(f"Combined narration track: {combined_path} ({size} bytes)")
            return combined_path, piece_wavs

        if piece_wavs:
            return piece_wavs[0]["path"], piece_wavs
        return None, []

    def _combine_pieces_sync(
        self,
        piece_wavs: list[dict],
        total_duration: float,
        output_path: str,
    ) -> bool:
        """Combine individual piece WAVs with silence padding into one track.

        AUDIO FORMAT STRATEGY:
        1. Each input piece is first normalized to 44100Hz stereo fltp
           using the NORMALIZE_FILTER from audio_utils.
        2. adelay places each piece at the correct timeline position.
        3. amix combines all pieces (same format -> no garbling).
        4. Output is forced to 44100Hz stereo PCM WAV.

        This prevents the chirpy/garbled audio caused by sample rate or
        channel count mismatches between pieces
        vs CosyVoice=44100Hz stereo).
        """
        from app.services.audio_utils import NORMALIZE_FILTER, STANDARD_SAMPLE_RATE, STANDARD_CHANNELS

        SR = str(STANDARD_SAMPLE_RATE)
        CH = str(STANDARD_CHANNELS)

        if len(piece_wavs) == 1:
            # Single piece: normalize -> delay -> pad to full duration
            p = piece_wavs[0]
            delay_ms = int(p["start_time"] * 1000)
            try:
                cmd = [
                    settings.FFMPEG_BIN, "-y",
                    "-i", p["path"],
                    "-af", f"{NORMALIZE_FILTER},adelay={delay_ms}|{delay_ms},apad=whole_dur={total_duration}",
                    "-ar", SR, "-ac", CH, "-acodec", "pcm_s16le",
                    output_path,
                ]
                logger.info(f"Combine single piece: delay={delay_ms}ms, dur={total_duration}s")
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode != 0:
                    logger.error(f"FFmpeg single piece combine error: {result.stderr[-300:]}")
                return result.returncode == 0
            except Exception as e:
                logger.error(f"FFmpeg single piece combine error: {e}")
                return False

        # Multiple pieces: normalize each -> adelay -> amix
        try:
            args = [settings.FFMPEG_BIN, "-y"]
            filter_parts = []

            for i, p in enumerate(piece_wavs):
                args.extend(["-i", p["path"]])
                delay_ms = int(p["start_time"] * 1000)
                # CRITICAL: normalize EACH piece to standard format BEFORE adelay
                # This prevents format mismatch in the downstream amix
                filter_parts.append(
                    f"[{i}:a]{NORMALIZE_FILTER},adelay={delay_ms}|{delay_ms}[d{i}]"
                )

            mix_inputs = "".join(f"[d{i}]" for i in range(len(piece_wavs)))
            filter_parts.append(
                f"{mix_inputs}amix=inputs={len(piece_wavs)}:duration=longest:normalize=0[out]"
            )

            filter_complex = ";".join(filter_parts)
            args.extend([
                "-filter_complex", filter_complex,
                "-map", "[out]",
                "-ar", SR, "-ac", CH, "-acodec", "pcm_s16le",
                "-t", str(total_duration),
                output_path,
            ])

            logger.info(f"Combine {len(piece_wavs)} pieces into timeline track, dur={total_duration}s")
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=120,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0:
                logger.error(f"FFmpeg combine error: {result.stderr[-300:]}")
            return result.returncode == 0

        except Exception as e:
            logger.error(f"FFmpeg combine exception: {e}")
            return False

    # --- Legacy methods (kept for compatibility) ---

    async def generate_narration_script(
        self,
        segment_info: list[dict],
        hook_type: str,
        total_duration: float,
        narration_hint: str = "",
    ) -> str:
        """Legacy: generate a single continuous narration script."""
        pieces = await self.generate_interspersed_script(
            segment_info, hook_type, total_duration,
            narration_ratio=100.0, narration_hint=narration_hint,
        )
        return " ".join(p["text"] for p in pieces)

    async def synthesize_tts(self, text: str, work_id: str = "", edge_voice: str = "zh-CN-XiaoxiaoNeural") -> str | None:
        """Legacy: synthesize a single continuous narration."""
        filename = f"narration_{work_id or uuid.uuid4().hex[:8]}.wav"
        output_path = str(self.output_dir / filename)
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None, _synthesize_edge_sync, text, edge_voice, output_path
        )
        if success:
            return output_path
        return None

    def get_audio_duration_sync(self, audio_path: str) -> float:
        try:
            cmd = [
                settings.FFPROBE_BIN, "-v", "quiet", "-print_format", "json",
                "-show_format", audio_path,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data.get("format", {}).get("duration", 0))
        except Exception as e:
            logger.warning(f"ffprobe duration error: {e}")
        return 0.0

    async def get_audio_duration(self, audio_path: str) -> float:
        return await asyncio.get_event_loop().run_in_executor(
            None, self.get_audio_duration_sync, audio_path
        )
