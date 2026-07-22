from __future__ import annotations

import pytest

from app.services import av_qa


@pytest.mark.asyncio
async def test_audio_nonzero_pts_is_rejected(monkeypatch):
    monkeypatch.setattr(
        av_qa,
        "probe_media",
        lambda _: {
            "fps": 25.0,
            "videoStreams": [
                {
                    "start_time": 0.0,
                    "start_pts": 0,
                    "nb_frames": 25,
                    "codec_name": "h264",
                    "pix_fmt": "yuv420p",
                }
            ],
            "audioStreams": [
                {
                    "start_time": 0.021,
                    "start_pts": 1024,
                    "sample_rate": 48_000,
                    "codec_name": "aac",
                }
            ],
        },
    )

    async def fake_samples(*args, **kwargs):
        return 48_000

    async def fake_noop(*args, **kwargs):
        return None

    monkeypatch.setattr(av_qa, "_decode_pcm_samples", fake_samples)
    monkeypatch.setattr(av_qa, "_decode_compatibility", fake_noop)
    result = await av_qa.validate_dubbed_media(
        "/tmp/not-read.mp4",
        expected_frames=25,
        check_loudness=False,
    )
    assert result["ok"] is False
    assert "audio does not start at PTS 0" in result["issues"]


@pytest.mark.asyncio
async def test_required_per_utterance_qa_fails_without_target_track(tmp_path, monkeypatch):
    from app.services.dubbing_timeline import build_utterance_timeline

    timeline = build_utterance_timeline(
        [
            {
                "id": "u1",
                "speakerId": "speaker-a",
                "text": "hello",
                "startFrame": 0,
                "endFrame": 25,
                "lipSyncPolicy": "required",
            }
        ],
        characters=[
            {
                "id": "a",
                "speakerId": "speaker-a",
                "name": "A",
                "voiceId": "a.wav",
            }
        ],
        total_frames=25,
    )

    async def fake_run(*args, **kwargs):
        return None

    monkeypatch.setattr(av_qa, "_run", fake_run)
    result = await av_qa.validate_utterance_qa(
        tmp_path / "missing.mp4",
        timeline=timeline,
        face_atlas={"tracks": []},
        asr_qa_url=None,
        syncnet_qa_url=None,
    )
    assert result["ok"] is False
    assert any("target face track is missing" in issue for issue in result["issues"])
