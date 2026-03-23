"""Review Engine - 3-layer fingerprint mutation check + deduplication + compliance.

Layer 1: Visual fingerprint check (video stream valid)
Layer 2: Audio fingerprint check (audio stream valid)
Layer 3: File metadata check (container-level uniqueness)
+ Self-check deduplication (internal DB)
+ Compliance engine (platform rules)
"""

import hashlib
import asyncio
import subprocess
import json
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger("review_engine")


class ReviewEngine:
    """Multi-layer review engine for remix works."""

    def __init__(self):
        self.ffprobe = settings.FFPROBE_BIN

    async def review_work(
        self,
        output_path: str,
        mutation_params: dict | None = None,
        existing_fingerprints: set[str] | None = None,
    ) -> dict:
        """Run all review checks on a rendered work."""
        result = {
            "visual_check_passed": False,
            "audio_check_passed": False,
            "metadata_check_passed": False,
            "dedup_check_passed": False,
            "compliance_check_passed": False,
            "overall_passed": False,
            "similarity_score": 0.0,
            "issues": [],
        }

        if not Path(output_path).exists():
            result["issues"].append("Output file does not exist")
            return result

        # Probe the file once, reuse for all checks
        probe_data = await self._probe_file(output_path)
        if not probe_data:
            result["issues"].append("Cannot probe output file")
            return result

        # Layer 1: Visual check
        visual_ok = self._check_visual(probe_data)
        result["visual_check_passed"] = visual_ok
        if not visual_ok:
            result["issues"].append("No valid video stream")

        # Layer 2: Audio check
        audio_ok = self._check_audio(probe_data)
        result["audio_check_passed"] = audio_ok
        if not audio_ok:
            result["issues"].append("No valid audio stream")

        # Layer 3: Metadata check
        meta_ok = self._check_metadata(probe_data)
        result["metadata_check_passed"] = meta_ok
        if not meta_ok:
            result["issues"].append("Invalid file metadata")

        # Dedup check
        file_hash = self._compute_file_hash(output_path)
        dedup_ok = True
        if existing_fingerprints and file_hash in existing_fingerprints:
            dedup_ok = False
            result["issues"].append("Duplicate file detected")
        result["dedup_check_passed"] = dedup_ok

        # Compliance check (platform rules)
        compliance_ok = self._check_compliance(probe_data)
        result["compliance_check_passed"] = compliance_ok
        if not compliance_ok:
            result["issues"].append("Does not meet platform compliance")

        # Overall
        result["overall_passed"] = all([
            visual_ok, audio_ok, meta_ok, dedup_ok, compliance_ok
        ])

        return result

    def _probe_file_sync(self, path: str) -> dict | None:
        """Run ffprobe synchronously (for thread pool, Windows compat)."""
        cmd = [
            self.ffprobe, "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", path
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            if result.returncode != 0:
                logger.warning(f"Review ffprobe failed for {path}: {result.stderr[:200]}")
                return None
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Review ffprobe exception for {path}: {type(e).__name__}: {e}")
            return None

    async def _probe_file(self, path: str) -> dict | None:
        """Async wrapper - runs sync probe in thread pool."""
        return await asyncio.get_event_loop().run_in_executor(None, self._probe_file_sync, path)

    def _check_visual(self, probe: dict) -> bool:
        """Check video stream exists and is valid."""
        for s in probe.get("streams", []):
            if s.get("codec_type") == "video":
                return bool(s.get("codec_name")) and int(s.get("width", 0)) > 0
        return False

    def _check_audio(self, probe: dict) -> bool:
        """Check audio stream exists and is valid."""
        for s in probe.get("streams", []):
            if s.get("codec_type") == "audio":
                return bool(s.get("codec_name"))
        return False

    def _check_metadata(self, probe: dict) -> bool:
        """Check file has valid format metadata."""
        fmt = probe.get("format", {})
        return (
            fmt.get("format_name") is not None
            and float(fmt.get("duration", 0)) > 0
            and int(fmt.get("size", 0)) > 0
        )

    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA-256 hash of file for deduplication."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def _check_compliance(self, probe: dict) -> bool:
        """Platform compliance checks.

        Rules for Douyin/Kuaishou short video:
        - Duration: 2s ~ 600s
        - File size: < 500MB
        - Must have both video and audio
        - Resolution: at least 240p height
        """
        fmt = probe.get("format", {})
        duration = float(fmt.get("duration", 0))
        size = int(fmt.get("size", 0))

        if duration < 2 or duration > 600:
            return False
        if size > 500 * 1024 * 1024:
            return False

        has_video = False
        has_audio = False
        for s in probe.get("streams", []):
            if s.get("codec_type") == "video":
                has_video = True
                if int(s.get("height", 0)) < 240:
                    return False
            if s.get("codec_type") == "audio":
                has_audio = True

        return has_video and has_audio
