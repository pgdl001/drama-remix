"""Remix Engine - Core logic for generating remix work plans.

V2: Story-coherent remix - maintains timeline order for narrative flow.
Segments are selected in chronological order with controlled variation,
producing coherent story progression instead of random jumps.
"""

import random
import hashlib
import uuid
from dataclasses import dataclass, field


@dataclass
class SegmentRef:
    """Reference to a material segment."""
    segment_id: str
    material_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    speed_factor: float = 1.0
    label: str = "body"


@dataclass
class RemixPlan:
    """A complete plan for one remix work."""
    work_id: str = ""
    segments: list[SegmentRef] = field(default_factory=list)
    hook_type: str = "suspense"
    transition_style: str = "cut"
    bgm_id: str | None = None
    bgm_volume: float = 0.15
    text_overlays: list[dict] = field(default_factory=list)
    total_duration: float = 0.0
    mutation_params: dict = field(default_factory=dict)
    fingerprint: str = ""
    # V2: narration metadata
    narration_hint: str = ""  # hint for LLM to generate narration


class RemixEngine:
    """Generates unique remix plans - V2 story-coherent mode."""

    HOOK_STRATEGIES = ["suspense", "question", "highlight", "emotion", "conflict"]
    TRANSITION_STYLES = ["cut", "fade", "dissolve", "zoom", "slide"]

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.duration_min = self.config.get("duration_range_min", 30)
        self.duration_max = self.config.get("duration_range_max", 60)
        self.speed_min = self.config.get("speed_min", 0.9)
        self.speed_max = self.config.get("speed_max", 1.1)

    def generate_plans(
        self,
        segments: list[dict],
        count: int,
        bgm_ids: list[str] | None = None,
        hook_strategy: str | None = None,
        existing_fingerprints: set[str] | None = None,
    ) -> list[RemixPlan]:
        """Generate `count` unique remix plans with story-coherent ordering."""
        if not segments:
            return []

        existing_fps = existing_fingerprints or set()
        plans = []
        attempts = 0
        max_attempts = count * 5

        while len(plans) < count and attempts < max_attempts:
            attempts += 1
            plan = self._generate_one_plan(segments, bgm_ids, hook_strategy)
            if plan.fingerprint not in existing_fps:
                plans.append(plan)
                existing_fps.add(plan.fingerprint)

        return plans

    def _generate_one_plan(
        self,
        segments: list[dict],
        bgm_ids: list[str] | None,
        hook_strategy: str | None,
    ) -> RemixPlan:
        """Generate a single story-coherent remix plan."""
        plan = RemixPlan(work_id=str(uuid.uuid4()))
        plan.hook_type = hook_strategy or random.choice(self.HOOK_STRATEGIES)
        target_duration = random.uniform(self.duration_min, self.duration_max)

        # V2: Story-coherent segment selection
        selected = self._select_segments_coherent(segments, target_duration, plan.hook_type)
        plan.segments = selected

        plan.total_duration = sum(
            (s.end_time - s.start_time) / s.speed_factor for s in selected
        )

        plan.transition_style = random.choice(self.TRANSITION_STYLES)

        if bgm_ids:
            plan.bgm_id = random.choice(bgm_ids)
            plan.bgm_volume = random.uniform(0.1, 0.25)

        plan.text_overlays = self._generate_text_overlays(plan)
        plan.mutation_params = self._generate_mutation_params()

        # Build narration hint from segment labels
        label_sequence = [s.label for s in selected]
        plan.narration_hint = self._build_narration_hint(plan.hook_type, label_sequence, plan.total_duration)

        plan.fingerprint = self._compute_fingerprint(plan)
        return plan

    def _select_segments_coherent(
        self, segments: list[dict], target_duration: float, hook_type: str
    ) -> list[SegmentRef]:
        """V2: Select segments maintaining story timeline order.
        
        Strategy:
        1. Group segments by material_id (each material = one episode)
        2. Sort within each group by start_time (timeline order)
        3. Pick a random starting point in the timeline
        4. Select consecutive segments from that point forward
        5. Optionally prepend a hook segment from a later dramatic moment
        
        This produces coherent story clips instead of random jumps.
        """
        selected = []
        accumulated = 0.0

        # Group by material, sort by timeline within each
        by_material: dict[str, list[dict]] = {}
        for s in segments:
            mid = s.get("material_id", "unknown")
            by_material.setdefault(mid, []).append(s)
        for mid in by_material:
            by_material[mid].sort(key=lambda x: x["start_time"])

        # Build a flat timeline: all segments across materials in order
        # For multi-episode: sort materials by ID (which usually preserves episode order)
        all_ordered = []
        for mid in sorted(by_material.keys()):
            all_ordered.extend(by_material[mid])

        if not all_ordered:
            return []

        total_segments = len(all_ordered)

        # Find hook/climax segments for potential hook opening
        hook_candidates = [
            (i, s) for i, s in enumerate(all_ordered)
            if s.get("label") in ("hook", "climax", "highlight")
        ]

        # Strategy: pick a starting window in the timeline
        # Use a random start offset to create variety between works
        # Allow starting from different points in the story
        max_start_idx = max(0, total_segments - 3)  # at least 3 segments ahead
        start_idx = random.randint(0, max_start_idx)

        # Optionally open with a hook segment (from near the start window or a dramatic moment)
        if hook_candidates and hook_type in ("suspense", "highlight", "emotion", "conflict"):
            # Pick a hook from the same region or slightly ahead (creates suspense)
            nearby_hooks = [
                (i, s) for i, s in hook_candidates
                if i >= start_idx and i < start_idx + total_segments // 3
            ]
            if nearby_hooks:
                hook_idx, hook_seg = random.choice(nearby_hooks)
                speed = random.uniform(self.speed_min, self.speed_max)
                ref = SegmentRef(
                    segment_id=hook_seg["id"],
                    material_id=hook_seg.get("material_id", ""),
                    start_time=hook_seg["start_time"],
                    end_time=hook_seg["end_time"],
                    speed_factor=speed,
                    label=hook_seg.get("label", "hook"),
                )
                seg_dur = (ref.end_time - ref.start_time) / ref.speed_factor
                selected.append(ref)
                accumulated += seg_dur
                # Advance start_idx past the hook to avoid immediate repetition
                start_idx = max(start_idx, hook_idx + 1)

        # Fill with consecutive timeline segments (story-coherent flow)
        # Add some controlled skip variation: occasionally skip 1 segment for pacing
        idx = start_idx
        skip_chance = 0.15  # 15% chance to skip a segment for pacing variety

        while accumulated < target_duration and idx < total_segments:
            seg = all_ordered[idx]
            idx += 1

            # Small chance to skip (for variety), but never skip hook/climax
            if random.random() < skip_chance and seg.get("label") == "body":
                continue

            speed = random.uniform(self.speed_min, self.speed_max)
            ref = SegmentRef(
                segment_id=seg["id"],
                material_id=seg.get("material_id", ""),
                start_time=seg["start_time"],
                end_time=seg["end_time"],
                speed_factor=speed,
                label=seg.get("label", "body"),
            )
            seg_dur = (ref.end_time - ref.start_time) / ref.speed_factor
            selected.append(ref)
            accumulated += seg_dur

        # If we wrapped around and still need more, take from beginning
        if accumulated < target_duration * 0.7 and start_idx > 0:
            for seg in all_ordered[:start_idx]:
                if accumulated >= target_duration:
                    break
                speed = random.uniform(self.speed_min, self.speed_max)
                ref = SegmentRef(
                    segment_id=seg["id"],
                    material_id=seg.get("material_id", ""),
                    start_time=seg["start_time"],
                    end_time=seg["end_time"],
                    speed_factor=speed,
                    label=seg.get("label", "body"),
                )
                seg_dur = (ref.end_time - ref.start_time) / ref.speed_factor
                selected.append(ref)
                accumulated += seg_dur

        return selected

    def _build_narration_hint(self, hook_type: str, labels: list[str], total_duration: float) -> str:
        """Build a hint string for LLM narration generation."""
        label_str = " -> ".join(labels) if labels else "body"
        return f"hook_type={hook_type}|labels={label_str}|duration={total_duration:.1f}s|segments={len(labels)}"

    def _generate_text_overlays(self, plan: RemixPlan) -> list[dict]:
        """Generate text overlay configs based on hook strategy."""
        overlays = []
        hook_texts = {
            "suspense": ["接下来的一幕让人窒息...", "你绝对想不到结局!", "看到最后我哭了..."],
            "question": ["他为什么要这样做?", "如果是你会怎么选?", "真相到底是什么?"],
            "highlight": ["全剧最燃片段!", "这段演技封神!", "高能预警!"],
            "emotion": ["泪目了...", "太感动了", "这才是真正的爱情"],
            "conflict": ["反转来了!", "大结局震撼!", "正义终将到来"],
        }
        texts = hook_texts.get(plan.hook_type, hook_texts["suspense"])
        overlays.append({
            "text": random.choice(texts),
            "position": "top_center",
            "start_time": 0,
            "duration": 3,
            "font_size": random.choice([24, 28, 32]),
            "color": random.choice(["#FFFFFF", "#FFD700", "#FF6B6B"]),
        })
        return overlays

    def _generate_mutation_params(self) -> dict:
        """Generate random mutation parameters for fingerprint uniqueness."""
        return {
            "visual": {
                "brightness": random.uniform(-0.05, 0.05),
                "contrast": random.uniform(0.95, 1.05),
                "saturation": random.uniform(0.95, 1.05),
                "hue_shift": random.uniform(-3, 3),
                "crop_percent": random.uniform(0.01, 0.03),
                "rotation_deg": random.uniform(-0.5, 0.5),
                "horizontal_flip": random.random() < 0.1,
                "noise_strength": random.uniform(0.001, 0.01),
            },
            "audio": {
                "pitch_shift_semitones": random.uniform(-0.3, 0.3),
                "tempo_factor": random.uniform(0.97, 1.03),
                "volume_db": random.uniform(-1.5, 1.5),
                "eq_low_gain": random.uniform(-2, 2),
                "eq_high_gain": random.uniform(-2, 2),
            },
            "metadata": {
                "unique_id": str(uuid.uuid4()),
                "creation_time_offset_seconds": random.randint(-3600, 3600),
            },
        }

    def _compute_fingerprint(self, plan: RemixPlan) -> str:
        """Compute a content fingerprint for deduplication."""
        content = (
            "|".join(f"{s.segment_id}:{s.speed_factor:.3f}" for s in plan.segments)
            + f"|{plan.hook_type}|{plan.bgm_id}"
            + f"|{plan.mutation_params.get('visual', {}).get('brightness', 0):.4f}"
            + f"|{plan.mutation_params.get('audio', {}).get('pitch_shift_semitones', 0):.4f}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:32]
