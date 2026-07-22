from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from app.services.dialogue_prompt import find_character, parse_dialogue_lines

PCM_SAMPLE_RATE = 48_000


def frames_to_samples(frames: int, *, fps: float, sample_rate: int = PCM_SAMPLE_RATE) -> int:
    return round(Fraction(frames) * sample_rate / Fraction(str(fps)))


def samples_to_frames(samples: int, *, sample_rate: int = PCM_SAMPLE_RATE, fps: float) -> int:
    return round(Fraction(samples) * Fraction(str(fps)) / sample_rate)


@dataclass(frozen=True)
class TimelineItem:
    index: int
    text: str
    speaker: str | None
    start_frame: int
    end_frame: int
    start_sample: int
    end_sample: int
    voice_id: str | None = None
    lip_sync_policy: str = "off"
    shot_index: int | None = None
    utterance_id: str | None = None
    speaker_id: str | None = None
    character_id: str | None = None
    face_track_id: str | None = None
    binding_confidence: float | None = None

    @property
    def duration_samples(self) -> int:
        return self.end_sample - self.start_sample


@dataclass(frozen=True)
class DubbingTimeline:
    fps: float
    sample_rate: int
    items: tuple[TimelineItem, ...]
    total_frames: int

    @property
    def duration_samples(self) -> int:
        return frames_to_samples(self.total_frames, fps=self.fps, sample_rate=self.sample_rate)


def build_timeline(
    segments: list[dict[str, Any]],
    *,
    fps: float = 25,
    sample_rate: int = PCM_SAMPLE_RATE,
    total_frames: int | None = None,
) -> DubbingTimeline:
    if fps <= 0 or sample_rate <= 0:
        raise ValueError("fps and sample_rate must be positive")
    items: list[TimelineItem] = []
    previous_end = 0
    for index, segment in enumerate(segments):
        start = int(segment.get("startFrame", 0))
        end = int(segment.get("endFrame", start))
        if start < 0:
            raise ValueError(f"segment {index} startFrame must be non-negative")
        if end <= start:
            raise ValueError(f"segment {index} must have endFrame > startFrame")
        if index and start < previous_end:
            raise ValueError(f"segment {index} overlap is not supported")
        policy = str(segment.get("lipSyncPolicy", "off"))
        if policy not in {"off", "preferred", "required"}:
            raise ValueError(f"invalid lipSyncPolicy: {policy}")
        text = str(segment.get("text") or "").strip()
        if not text:
            raise ValueError(f"segment {index} text is required")
        items.append(
            TimelineItem(
                index=index,
                text=text,
                speaker=segment.get("speaker"),
                start_frame=start,
                end_frame=end,
                start_sample=frames_to_samples(start, fps=fps, sample_rate=sample_rate),
                end_sample=frames_to_samples(end, fps=fps, sample_rate=sample_rate),
                voice_id=segment.get("voiceId"),
                lip_sync_policy=policy,
                shot_index=segment.get("shotIndex"),
                utterance_id=segment.get("id"),
                speaker_id=segment.get("speakerId"),
                character_id=segment.get("characterId"),
                face_track_id=segment.get("faceTrackId"),
                binding_confidence=segment.get("bindingConfidence"),
            )
        )
        previous_end = end
    required_frames = max((item.end_frame for item in items), default=0)
    if total_frames is not None and total_frames < required_frames:
        raise ValueError("total_frames cannot end before a dialogue")
    return DubbingTimeline(
        fps=fps,
        sample_rate=sample_rate,
        items=tuple(items),
        total_frames=total_frames if total_frames is not None else required_frames,
    )


def build_utterance_timeline(
    utterances: list[dict[str, Any]],
    *,
    characters: list[dict[str, Any]],
    total_frames: int,
    fps: float = 25,
    sample_rate: int = PCM_SAMPLE_RATE,
) -> DubbingTimeline:
    """Build a strict, non-overlapping production timeline.

    ``speakerId`` is the canonical identity. Display-name matching is intentionally
    excluded here and remains available only through the legacy dialogue adapter.
    """
    by_speaker: dict[str, dict[str, Any]] = {}
    for character in characters:
        speaker_id = str(character.get("speakerId") or character.get("id") or "").strip()
        if not speaker_id:
            raise ValueError("character speakerId/id is required")
        if speaker_id in by_speaker:
            raise ValueError(f"duplicate speakerId: {speaker_id}")
        by_speaker[speaker_id] = character

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, utterance in enumerate(utterances):
        utterance_id = str(utterance.get("id") or "").strip()
        if not utterance_id:
            raise ValueError(f"utterance {index} id is required")
        if utterance_id in seen_ids:
            raise ValueError(f"duplicate utterance id: {utterance_id}")
        seen_ids.add(utterance_id)
        speaker_id = str(utterance.get("speakerId") or "").strip()
        character = by_speaker.get(speaker_id)
        if character is None:
            raise ValueError(f"unknown speakerId: {speaker_id}")
        normalized.append(
            {
                **utterance,
                "id": utterance_id,
                "speaker": character.get("name"),
                "speakerId": speaker_id,
                "characterId": character.get("id"),
                "voiceId": character.get("voiceId") or None,
                "faceTrackId": utterance.get("faceTrackId") or character.get("faceTrackId"),
            }
        )
    normalized.sort(key=lambda item: (int(item["startFrame"]), int(item["endFrame"])))
    return build_timeline(
        normalized,
        fps=fps,
        sample_rate=sample_rate,
        total_frames=total_frames,
    )


def build_dialogue_timeline(
    *,
    dialogues: list[dict[str, Any]],
    timeline_map: list[dict[str, Any]],
    characters: list[dict[str, Any]],
    total_frames: int,
    fps: float = 25,
    sample_rate: int = PCM_SAMPLE_RATE,
) -> DubbingTimeline:
    mapped_ranges: list[dict[str, int]] = []
    for index, item in enumerate(timeline_map):
        if item.get("outputStartSec") is not None and item.get("outputEndSec") is not None:
            start = round(float(item["outputStartSec"]) * fps)
            end = round(float(item["outputEndSec"]) * fps)
        else:
            start = int(item["outputStartFrame"])
            end = int(item["outputEndFrame"])
        mapped_ranges.append(
            {"segmentIndex": int(item.get("segmentIndex", index)), "start": start, "end": end}
        )
    mapped_ranges.sort(key=lambda item: item["start"])
    for index in range(len(mapped_ranges) - 1):
        mapped_ranges[index]["end"] = min(
            mapped_ranges[index]["end"], mapped_ranges[index + 1]["start"]
        )
    by_segment = {item["segmentIndex"]: item for item in mapped_ranges}
    segments: list[dict[str, Any]] = []
    for dialogue in dialogues:
        shot_index = int(dialogue.get("shotIndex", 0))
        mapped = by_segment.get(shot_index)
        explicit = dialogue.get("startFrame") is not None and dialogue.get("endFrame") is not None
        if explicit:
            slot_start = int(dialogue["startFrame"])
            slot_end = int(dialogue["endFrame"])
        elif mapped:
            slot_start = mapped["start"]
            slot_end = mapped["end"]
        else:
            raise ValueError(f"dialogue shotIndex {shot_index} has no timelineMap entry")
        lines = parse_dialogue_lines(dialogue.get("text"))
        if not lines:
            continue
        slot_frames = slot_end - slot_start
        if slot_frames < len(lines):
            raise ValueError(f"dialogue shotIndex {shot_index} slot is too short")
        policy = dialogue.get("lipSyncPolicy") or "off"
        if policy not in {"off", "preferred", "required"}:
            raise ValueError(f"invalid lipSyncPolicy: {policy}")
        for index, line in enumerate(lines):
            start = slot_start + slot_frames * index // len(lines)
            end = slot_start + slot_frames * (index + 1) // len(lines)
            character = find_character(characters, line["speaker"])
            segments.append(
                {
                    "text": line["line"],
                    "speaker": line["speaker"] or None,
                    "voiceId": (character or {}).get("voiceId"),
                    "startFrame": start,
                    "endFrame": end,
                    "lipSyncPolicy": policy,
                    "shotIndex": shot_index,
                }
            )
    segments.sort(key=lambda item: (item["startFrame"], item["endFrame"]))
    return build_timeline(
        segments,
        fps=fps,
        sample_rate=sample_rate,
        total_frames=total_frames,
    )
