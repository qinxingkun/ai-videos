from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

try:
    import numpy as np
except ImportError:  # Optional until a FaceAtlas request is made.
    np = None

from app.config import Settings
from app.services.character_qa import _cosine, _get_app, _biggest_face_embedding


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def _center_distance(a: np.ndarray, b: np.ndarray, width: int, height: int) -> float:
    ax, ay = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    diagonal = max(1.0, math.hypot(width, height))
    return min(1.0, math.hypot(ax - bx, ay - by) / diagonal)


def _assign(cost: np.ndarray) -> list[tuple[int, int]]:
    if not cost.size:
        return []
    try:
        from scipy.optimize import linear_sum_assignment

        rows, cols = linear_sum_assignment(cost)
        return list(zip(rows.tolist(), cols.tolist()))
    except Exception:
        pairs: list[tuple[int, int]] = []
        remaining_rows, remaining_cols = set(range(cost.shape[0])), set(range(cost.shape[1]))
        while remaining_rows and remaining_cols:
            row, col = min(
                ((r, c) for r in remaining_rows for c in remaining_cols),
                key=lambda pair: float(cost[pair]),
            )
            pairs.append((row, col))
            remaining_rows.remove(row)
            remaining_cols.remove(col)
        return pairs


def _smooth_observations(observations: list[dict[str, Any]]) -> None:
    boxes = np.asarray([item["bbox"] for item in observations], dtype="float64")
    for index, item in enumerate(observations):
        lo, hi = max(0, index - 2), min(len(boxes), index + 3)
        item["bbox"] = [round(float(value), 2) for value in np.median(boxes[lo:hi], axis=0)]


def _save_representative(
    video_path: Path,
    track_id: str,
    observation: dict[str, Any],
    output_dir: Path,
) -> str | None:
    import cv2

    capture = cv2.VideoCapture(str(video_path))
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(observation["frameIndex"]))
        ok, frame = capture.read()
        if not ok:
            return None
        x1, y1, x2, y2 = [int(round(v)) for v in observation["bbox"]]
        height, width = frame.shape[:2]
        margin_x, margin_y = max(12, (x2 - x1) // 3), max(12, (y2 - y1) // 3)
        crop = frame[
            max(0, y1 - margin_y):min(height, y2 + margin_y),
            max(0, x1 - margin_x):min(width, x2 + margin_x),
        ]
        if crop.size == 0:
            return None
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{track_id}.jpg"
        return path.name if cv2.imwrite(str(path), crop) else None
    finally:
        capture.release()


def build_face_atlas(
    video_path: str | Path,
    *,
    output_dir: str | Path,
    settings: Settings,
) -> dict[str, Any]:
    """Detect every face and build stable tracks using IOU, motion and ArcFace."""
    import cv2

    if np is None:
        return {"ok": False, "reason": "numpy unavailable", "tracks": []}
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    app = _get_app()
    if app is None:
        return {"ok": False, "reason": "InsightFace unavailable", "tracks": []}

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video for face tracking: {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    active: list[dict[str, Any]] = []
    finished: list[dict[str, Any]] = []
    next_track = 0
    frame_index = 0
    max_gap = settings.face_track_max_gap_frames
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            detections = []
            for face in app.get(frame):
                embedding = getattr(face, "normed_embedding", None)
                if embedding is None:
                    continue
                bbox = np.asarray(face.bbox, dtype="float64")
                if min(bbox[2] - bbox[0], bbox[3] - bbox[1]) < settings.face_track_min_size:
                    continue
                detections.append(
                    {
                        "bbox": bbox,
                        "embedding": np.asarray(embedding, dtype="float64"),
                        "score": float(getattr(face, "det_score", 0.0)),
                    }
                )

            costs = np.full((len(active), len(detections)), 10.0, dtype="float64")
            for row, track in enumerate(active):
                for col, detection in enumerate(detections):
                    similarity = _cosine(track["embedding"], detection["embedding"])
                    overlap = _iou(track["bbox"], detection["bbox"])
                    distance = _center_distance(track["bbox"], detection["bbox"], width, height)
                    if similarity >= settings.face_track_reid_threshold or overlap >= 0.08:
                        costs[row, col] = 0.5 * (1 - similarity) + 0.35 * (1 - overlap) + 0.15 * distance

            matched_tracks: set[int] = set()
            matched_detections: set[int] = set()
            for row, col in _assign(costs):
                if costs[row, col] > settings.face_track_assignment_cost:
                    continue
                track, detection = active[row], detections[col]
                track["bbox"] = detection["bbox"]
                track["embedding"] = (
                    0.85 * track["embedding"] + 0.15 * detection["embedding"]
                )
                norm = np.linalg.norm(track["embedding"])
                if norm:
                    track["embedding"] /= norm
                track["missed"] = 0
                track["observations"].append(
                    {
                        "frameIndex": frame_index,
                        "bbox": detection["bbox"].tolist(),
                        "confidence": round(detection["score"], 4),
                    }
                )
                matched_tracks.add(row)
                matched_detections.add(col)

            survivors: list[dict[str, Any]] = []
            for row, track in enumerate(active):
                if row not in matched_tracks:
                    track["missed"] += 1
                if track["missed"] <= max_gap:
                    survivors.append(track)
                else:
                    finished.append(track)
            active = survivors
            for col, detection in enumerate(detections):
                if col in matched_detections:
                    continue
                track_id = f"track_{next_track}"
                next_track += 1
                active.append(
                    {
                        "id": track_id,
                        "bbox": detection["bbox"],
                        "embedding": detection["embedding"],
                        "missed": 0,
                        "observations": [
                            {
                                "frameIndex": frame_index,
                                "bbox": detection["bbox"].tolist(),
                                "confidence": round(detection["score"], 4),
                            }
                        ],
                    }
                )
            frame_index += 1
    finally:
        capture.release()
    finished.extend(active)

    public_tracks: list[dict[str, Any]] = []
    for track in finished:
        observations = track["observations"]
        if len(observations) < settings.face_track_min_frames:
            continue
        _smooth_observations(observations)
        representative = max(
            observations,
            key=lambda item: (item["bbox"][2] - item["bbox"][0])
            * (item["bbox"][3] - item["bbox"][1]),
        )
        thumbnail = _save_representative(video_path, track["id"], representative, output_dir)
        visible_ratio = len(observations) / max(1, total_frames)
        public_tracks.append(
            {
                "id": track["id"],
                "frameCount": len(observations),
                "visibleRatio": round(visible_ratio, 4),
                "firstFrame": observations[0]["frameIndex"],
                "lastFrame": observations[-1]["frameIndex"],
                "representativeFrame": representative["frameIndex"],
                "thumbnail": thumbnail,
                "observations": observations,
                "_embedding": track["embedding"],
            }
        )
    public_tracks.sort(key=lambda track: (-track["frameCount"], track["id"]))
    digest = hashlib.sha256()
    with video_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "ok": True,
        "videoHash": digest.hexdigest(),
        "fps": fps,
        "width": width,
        "height": height,
        "totalFrames": total_frames,
        "tracks": public_tracks,
    }


def bind_characters_to_tracks(
    characters: list[dict[str, Any]],
    atlas: dict[str, Any],
    *,
    settings: Settings,
    reference_resolver,
    overrides: dict[str, str] | None = None,
    mode: str = "auto",
) -> list[dict[str, Any]]:
    overrides = overrides or {}
    tracks = atlas.get("tracks") or []
    by_id = {track["id"]: track for track in tracks}
    claimed: set[str] = set()
    binding_by_speaker: dict[str, dict[str, Any]] = {}
    pending: list[tuple[dict[str, Any], Any]] = []
    for character in characters:
        speaker_id = str(character.get("speakerId") or character.get("id") or "")
        manual = overrides.get(speaker_id) or character.get("faceTrackId")
        if manual:
            valid = manual in by_id and manual not in claimed
            if valid:
                claimed.add(manual)
            binding_by_speaker[speaker_id] = {
                "speakerId": speaker_id,
                "faceTrackId": manual if valid else None,
                "confidence": 1.0 if valid else 0.0,
                "status": "manual" if valid else "binding_required",
                "reason": None if valid else "manual faceTrackId is missing or already claimed",
            }
            continue
        if mode == "off":
            binding_by_speaker[speaker_id] = {
                "speakerId": speaker_id,
                "faceTrackId": None,
                "confidence": None,
                "status": "off",
            }
            continue
        reference_name = character.get("referenceImageName")
        reference = reference_resolver(reference_name) if reference_name else None
        app = _get_app() if reference else None
        reference_embedding = (
            _biggest_face_embedding(app, reference) if app is not None and reference else None
        )
        if reference_embedding is None:
            binding_by_speaker[speaker_id] = {
                "speakerId": speaker_id,
                "faceTrackId": None,
                "confidence": 0.0,
                "status": "binding_required",
                "reason": "reference image is missing or contains no face",
            }
            continue
        pending.append((character, reference_embedding))

    available_tracks = [track for track in tracks if track["id"] not in claimed]
    if pending and available_tracks:
        similarities = np.asarray(
            [
                [
                    _cosine(reference_embedding, track["_embedding"])
                    for track in available_tracks
                ]
                for _, reference_embedding in pending
            ],
            dtype="float64",
        )
        assignments = _assign(1.0 - similarities)
        assigned_rows = {row: col for row, col in assignments}
    else:
        similarities = np.empty((len(pending), len(available_tracks)))
        assigned_rows = {}

    for row, (character, _) in enumerate(pending):
        speaker_id = str(character.get("speakerId") or character.get("id") or "")
        col = assigned_rows.get(row)
        best_track = available_tracks[col] if col is not None else None
        best_score = float(similarities[row, col]) if col is not None else 0.0
        row_scores = sorted(
            [float(value) for value in similarities[row]],
            reverse=True,
        )
        second_score = row_scores[1] if len(row_scores) > 1 else -1.0
        threshold = float(
            character.get("bindingThreshold")
            if character.get("bindingThreshold") is not None
            else settings.face_binding_threshold
        )
        confident = (
            best_track is not None
            and best_score >= threshold
            and best_score - second_score >= settings.face_binding_margin
        )
        binding_by_speaker[speaker_id] = {
            "speakerId": speaker_id,
            "faceTrackId": best_track["id"] if confident else None,
            "candidateTrackId": best_track["id"] if best_track else None,
            "confidence": round(best_score, 4),
            "status": "auto" if confident else "binding_required",
            "reason": None if confident else "binding confidence is below threshold or ambiguous",
        }
    return [
        binding_by_speaker[str(character.get("speakerId") or character.get("id") or "")]
        for character in characters
    ]


def public_face_atlas(atlas: dict[str, Any]) -> dict[str, Any]:
    return {
        **atlas,
        "tracks": [
            {key: value for key, value in track.items() if not key.startswith("_")}
            for track in atlas.get("tracks") or []
        ],
    }


def evaluate_track_preservation(
    original_path: str | Path,
    rendered_path: str | Path,
    *,
    start_frame: int,
    end_frame: int,
    track: dict[str, Any],
) -> dict[str, Any]:
    """Measure target identity retention and non-target pixel protection."""
    import cv2

    app = _get_app()
    if app is None or np is None:
        return {"ok": True, "skipped": True, "reason": "face QA dependencies unavailable"}
    observations = {
        int(item["frameIndex"]): item["bbox"]
        for item in track.get("observations") or []
        if start_frame <= int(item["frameIndex"]) < end_frame
    }
    sample_frames = sorted(observations)
    if len(sample_frames) > 3:
        sample_frames = [
            sample_frames[0],
            sample_frames[len(sample_frames) // 2],
            sample_frames[-1],
        ]
    original = cv2.VideoCapture(str(original_path))
    rendered = cv2.VideoCapture(str(rendered_path))
    similarities: list[float] = []
    non_target_diffs: list[float] = []
    try:
        for frame_index in sample_frames:
            original.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            rendered.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok_a, frame_a = original.read()
            ok_b, frame_b = rendered.read()
            if not ok_a or not ok_b:
                continue
            x1, y1, x2, y2 = [int(round(value)) for value in observations[frame_index]]
            height, width = frame_a.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(width, x2), min(height, y2)
            crop_a, crop_b = frame_a[y1:y2, x1:x2], frame_b[y1:y2, x1:x2]
            if crop_a.size and crop_b.size:
                faces_a, faces_b = app.get(crop_a), app.get(crop_b)
                if faces_a and faces_b:
                    face_a = max(faces_a, key=lambda face: float(np.prod(face.bbox[2:] - face.bbox[:2])))
                    face_b = max(faces_b, key=lambda face: float(np.prod(face.bbox[2:] - face.bbox[:2])))
                    similarities.append(
                        _cosine(face_a.normed_embedding, face_b.normed_embedding)
                    )
            mask = np.ones(frame_a.shape[:2], dtype=bool)
            margin_x, margin_y = max(4, (x2 - x1) // 4), max(4, (y2 - y1) // 4)
            mask[
                max(0, y1 - margin_y):min(height, y2 + margin_y),
                max(0, x1 - margin_x):min(width, x2 + margin_x),
            ] = False
            if mask.any():
                diff = np.abs(frame_a.astype("float32") - frame_b.astype("float32"))
                non_target_diffs.append(float(diff[mask].mean()))
    finally:
        original.release()
        rendered.release()
    identity_min = min(similarities) if similarities else None
    outside_mean = (
        sum(non_target_diffs) / len(non_target_diffs) if non_target_diffs else None
    )
    issues = []
    if identity_min is not None and identity_min < 0.30:
        issues.append(f"target identity similarity {identity_min:.3f} < 0.30")
    if outside_mean is not None and outside_mean > 12.0:
        issues.append(f"non-target mean pixel difference {outside_mean:.2f} > 12.0")
    return {
        "ok": not issues,
        "skipped": not sample_frames,
        "identityMinSimilarity": round(identity_min, 4) if identity_min is not None else None,
        "nonTargetMeanAbsDiff": round(outside_mean, 3) if outside_mean is not None else None,
        "sampledFrames": len(sample_frames),
        "issues": issues,
    }
