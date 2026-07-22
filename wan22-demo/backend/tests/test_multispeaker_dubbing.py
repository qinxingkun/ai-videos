from __future__ import annotations

from pathlib import Path
import json

import pytest
from pydantic import ValidationError

from app.schemas.api import DubRequest, DubUtterance
from app.services.dubbing_timeline import build_utterance_timeline
from app.services.lipsync import _track_boxes_for_item
from app.services.concat_video import _build_smart_splice_filter


CHARACTERS = [
    {
        "id": "hero-a",
        "speakerId": "speaker-a",
        "name": "甲",
        "voiceId": "a.wav",
        "faceTrackId": "track_0",
    },
    {
        "id": "hero-b",
        "speakerId": "speaker-b",
        "name": "乙",
        "voiceId": "b.wav",
        "faceTrackId": "track_1",
    },
]


def test_structured_utterances_bind_stable_speaker_voice_and_track():
    timeline = build_utterance_timeline(
        [
            {
                "id": "u1",
                "speakerId": "speaker-a",
                "text": "第一句",
                "startFrame": 0,
                "endFrame": 25,
                "lipSyncPolicy": "required",
            },
            {
                "id": "u2",
                "speakerId": "speaker-b",
                "text": "第二句",
                "startFrame": 25,
                "endFrame": 50,
                "lipSyncPolicy": "preferred",
            },
        ],
        characters=CHARACTERS,
        total_frames=50,
    )
    assert [item.speaker_id for item in timeline.items] == ["speaker-a", "speaker-b"]
    assert [item.voice_id for item in timeline.items] == ["a.wav", "b.wav"]
    assert [item.face_track_id for item in timeline.items] == ["track_0", "track_1"]


def test_structured_utterances_reject_overlap_and_unknown_speaker():
    with pytest.raises(ValueError, match="overlap"):
        build_utterance_timeline(
            [
                {"id": "u1", "speakerId": "speaker-a", "text": "a", "startFrame": 0, "endFrame": 20},
                {"id": "u2", "speakerId": "speaker-b", "text": "b", "startFrame": 19, "endFrame": 30},
            ],
            characters=CHARACTERS,
            total_frames=50,
        )
    with pytest.raises(ValueError, match="unknown speakerId"):
        build_utterance_timeline(
            [{"id": "u1", "speakerId": "missing", "text": "a", "startFrame": 0, "endFrame": 20}],
            characters=CHARACTERS,
            total_frames=50,
        )


def test_dub_schema_rejects_invalid_policy_and_mode():
    with pytest.raises(ValidationError):
        DubUtterance(
            id="u1",
            speakerId="speaker-a",
            text="x",
            startFrame=0,
            endFrame=25,
            lipSyncPolicy="sometimes",
        )
    with pytest.raises(ValidationError):
        DubRequest(path="/tmp/a.mp4", ttsMode="silent")


def test_track_boxes_interpolate_short_detection_gaps():
    timeline = build_utterance_timeline(
        [{"id": "u1", "speakerId": "speaker-a", "text": "x", "startFrame": 0, "endFrame": 3}],
        characters=CHARACTERS,
        total_frames=3,
    )
    track = {
        "id": "track_0",
        "observations": [
            {"frameIndex": 0, "bbox": [0, 0, 10, 10]},
            {"frameIndex": 2, "bbox": [2, 2, 12, 12]},
        ],
    }
    boxes = _track_boxes_for_item(timeline.items[0], track, visible_ratio_min=0.6)
    assert boxes[1] == [1.0, 1.0, 11.0, 11.0]


def test_smart_splice_audio_filter_never_uses_async_resample():
    filter_graph, audio_label, _ = _build_smart_splice_filter(
        2,
        [
            {"start": 0.0, "duration": 1.0},
            {"start": 0.0, "duration": 1.0},
        ],
        with_audio=True,
        width=320,
        height=180,
        audio_crossfade_sec=0.05,
        audio_edge_fade_sec=0.03,
        micro_video_fade_sec=0.08,
    )
    assert audio_label == "[aout]"
    assert "aresample=async" not in filter_graph
    assert "aresample=48000:first_pts=0" in filter_graph


def test_two_person_production_fixture_is_valid_and_non_overlapping():
    fixture = (
        Path(__file__).parents[1]
        / "data"
        / "fixtures"
        / "dubbing"
        / "two_person_sequential.json"
    )
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    timeline = build_utterance_timeline(
        payload["utterances"],
        characters=payload["characters"],
        total_frames=125,
    )
    assert len(timeline.items) == 2
    assert timeline.items[0].end_frame <= timeline.items[1].start_frame


@pytest.mark.asyncio
async def test_analyze_session_persists_binding_required(monkeypatch, tmp_path: Path):
    from app.config import Settings
    from app.services import dubbing_session

    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    settings = Settings(
        comfyui_root=tmp_path / "ComfyUI",
        dubbing_sessions_dir=tmp_path / "sessions",
    )

    async def fake_master(source_path, output, settings=None):
        Path(output).write_bytes(b"master")
        return {"path": str(output), "degraded": False, "method": "test", "fps": 25}

    monkeypatch.setattr(dubbing_session, "create_visual_master", fake_master)
    monkeypatch.setattr(
        dubbing_session,
        "build_face_atlas",
        lambda *args, **kwargs: {"ok": True, "tracks": [], "totalFrames": 25},
    )
    result = await dubbing_session.analyze_dub_session(
        {
            "media": {"filename": source.name, "path": str(source)},
            "characters": [
                {
                    "id": "hero-a",
                    "speakerId": "speaker-a",
                    "name": "甲",
                    "voiceId": "a.wav",
                    "referenceImageName": "a.png",
                }
            ],
        },
        settings=settings,
    )
    assert result["status"] == "awaiting_binding"
    assert (settings.dubbing_sessions_dir / result["sessionId"] / "manifest.json").is_file()


def _write_awaiting_session(tmp_path: Path, *, with_tracks: bool = True):
    from app.config import Settings

    sessions = tmp_path / "sessions"
    session_id = "dub_test_session"
    directory = sessions / session_id
    directory.mkdir(parents=True)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    master = directory / "visual_master.mp4"
    master.write_bytes(b"master")
    tracks = (
        [{"id": "track_0"}, {"id": "track_1"}]
        if with_tracks
        else []
    )
    manifest = {
        "version": 1,
        "sessionId": session_id,
        "status": "awaiting_binding",
        "createdAt": 0,
        "source": str(source),
        "visualMaster": {"path": str(master), "fps": 25},
        "visualMasterPath": str(master),
        "faceAtlas": {"ok": True, "tracks": tracks, "totalFrames": 250},
        "characters": CHARACTERS,
        "bindings": [
            {
                "speakerId": "speaker-a",
                "faceTrackId": None,
                "status": "binding_required",
                "confidence": 0.4,
                "reason": "ambiguous",
            },
            {
                "speakerId": "speaker-b",
                "faceTrackId": None,
                "status": "binding_required",
                "confidence": 0.35,
                "reason": "ambiguous",
            },
        ],
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    settings = Settings(comfyui_root=tmp_path / "ComfyUI", dubbing_sessions_dir=sessions)
    return settings, manifest


@pytest.mark.asyncio
async def test_render_blocks_required_unbound_with_structured_last_error(tmp_path: Path):
    from app.services import dubbing_session
    from app.services.dubbing_session import DubbingSessionError

    settings, manifest = _write_awaiting_session(tmp_path)
    with pytest.raises(DubbingSessionError) as raised:
        await dubbing_session.render_dub_session(
            {
                "sessionId": manifest["sessionId"],
                "characters": CHARACTERS,
                "utterances": [
                    {
                        "id": "u1",
                        "speakerId": "speaker-a",
                        "text": "第一句",
                        "startFrame": 0,
                        "endFrame": 40,
                        "lipSyncPolicy": "required",
                    }
                ],
            },
            settings=settings,
        )
    err = raised.value
    assert err.code == "BINDING_REQUIRED"
    assert err.http_status == 409
    assert err.utterance_ids == ["u1"]
    assert err.to_detail()["sessionId"] == manifest["sessionId"]
    stored = dubbing_session.load_dub_session(manifest["sessionId"], settings=settings)
    assert stored["status"] == "awaiting_binding"
    assert stored["lastError"]["code"] == "BINDING_REQUIRED"
    assert stored["lastError"]["utteranceIds"] == ["u1"]


@pytest.mark.asyncio
async def test_render_manual_override_succeeds(monkeypatch, tmp_path: Path):
    from app.services import dubbing_session

    settings, manifest = _write_awaiting_session(tmp_path)
    captured = {}

    async def fake_dub(body, settings=None):
        captured["body"] = body
        return {"ok": True, "filename": "dub_out.mp4", "metrics": {}}

    monkeypatch.setattr(dubbing_session, "dub_media", fake_dub)
    result = await dubbing_session.render_dub_session(
        {
            "sessionId": manifest["sessionId"],
            "characters": CHARACTERS,
            "bindingOverrides": {"speaker-a": "track_0", "speaker-b": "track_1"},
            "utterances": [
                {
                    "id": "u1",
                    "speakerId": "speaker-a",
                    "text": "第一句",
                    "startFrame": 0,
                    "endFrame": 40,
                    "lipSyncPolicy": "required",
                },
                {
                    "id": "u2",
                    "speakerId": "speaker-b",
                    "text": "第二句",
                    "startFrame": 40,
                    "endFrame": 80,
                    "lipSyncPolicy": "required",
                },
            ],
        },
        settings=settings,
    )
    assert result["ok"] is True
    assert captured["body"]["utterances"][0]["faceTrackId"] == "track_0"
    assert captured["body"]["utterances"][1]["faceTrackId"] == "track_1"
    stored = dubbing_session.load_dub_session(manifest["sessionId"], settings=settings)
    assert stored["status"] == "done"
    assert stored["lastError"] is None
    assert {item["speakerId"]: item["status"] for item in stored["bindings"]} == {
        "speaker-a": "manual",
        "speaker-b": "manual",
    }


@pytest.mark.asyncio
async def test_render_preferred_unbound_can_deliver(monkeypatch, tmp_path: Path):
    from app.services import dubbing_session

    settings, manifest = _write_awaiting_session(tmp_path)
    captured = {}

    async def fake_dub(body, settings=None):
        captured["body"] = body
        return {
            "ok": True,
            "filename": "dub_pref.mp4",
            "metrics": {},
            "fallbacks": [{"utteranceId": "u-pref", "reason": "no faceTrackId"}],
        }

    monkeypatch.setattr(dubbing_session, "dub_media", fake_dub)
    result = await dubbing_session.render_dub_session(
        {
            "sessionId": manifest["sessionId"],
            "characters": CHARACTERS,
            "utterances": [
                {
                    "id": "u-pref",
                    "speakerId": "speaker-a",
                    "text": "可降级句",
                    "startFrame": 0,
                    "endFrame": 30,
                    "lipSyncPolicy": "preferred",
                }
            ],
        },
        settings=settings,
    )
    assert result["ok"] is True
    assert captured["body"]["utterances"][0].get("faceTrackId") in (None, "")
    stored = dubbing_session.load_dub_session(manifest["sessionId"], settings=settings)
    assert stored["status"] == "done"


@pytest.mark.asyncio
async def test_render_records_structured_av_qa_failure(monkeypatch, tmp_path: Path):
    from app.services import dubbing_session
    from app.services.dubbing_session import DubbingSessionError

    settings, manifest = _write_awaiting_session(tmp_path)

    async def fake_dub(body, settings=None):
        raise RuntimeError("AV QA failed: utterance u1 syncnet; utterance u2 asr")

    monkeypatch.setattr(dubbing_session, "dub_media", fake_dub)
    with pytest.raises(DubbingSessionError) as raised:
        await dubbing_session.render_dub_session(
            {
                "sessionId": manifest["sessionId"],
                "characters": CHARACTERS,
                "bindingOverrides": {"speaker-a": "track_0"},
                "utterances": [
                    {
                        "id": "u1",
                        "speakerId": "speaker-a",
                        "text": "质检失败句",
                        "startFrame": 0,
                        "endFrame": 25,
                        "lipSyncPolicy": "required",
                    }
                ],
            },
            settings=settings,
        )
    err = raised.value
    assert err.code == "AV_QA_FAILED"
    assert err.http_status == 422
    stored = dubbing_session.load_dub_session(manifest["sessionId"], settings=settings)
    assert stored["status"] == "error"
    assert stored["lastError"]["code"] == "AV_QA_FAILED"
    assert "u1" in stored["lastError"]["utteranceIds"]


def test_classify_required_lipsync_failure():
    from app.services.dubbing_session import _classify_render_exception

    err = _classify_render_exception(
        RuntimeError("required LatentSync failed for utterance u9"),
        session_id="dub_x",
    )
    assert err.code == "REQUIRED_LIPSYNC_FAILED"
    assert err.http_status == 422


def test_multishot_two_person_i2v_fixture_timeline():
    fixture = (
        Path(__file__).parents[1]
        / "data"
        / "fixtures"
        / "dubbing"
        / "multishot_two_person_i2v.json"
    )
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    timeline = build_utterance_timeline(
        payload["utterances"],
        characters=payload["characters"],
        total_frames=payload["expected"]["totalFrames"],
    )
    assert len(timeline.items) == 4
    assert payload["mode"] == "i2v"
    assert timeline.items[0].end_frame <= timeline.items[1].start_frame
    assert timeline.items[-1].end_frame <= payload["expected"]["totalFrames"]
    assert all(
        timeline.items[i].end_frame <= timeline.items[i + 1].start_frame
        for i in range(len(timeline.items) - 1)
    )
