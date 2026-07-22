from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.concat_video import _build_timeline_map
from app.services.dubbing_timeline import build_timeline, frames_to_samples, samples_to_frames
from app.services.media_probe import probe_media
from app.services.tts_provider import ProviderUnavailable, create_tts_provider


def test_probe_returns_stream_timing_and_does_not_invent_24fps(monkeypatch):
    payload = {
        "streams": [
            {
                "index": 0, "codec_type": "video", "codec_name": "h264",
                "pix_fmt": "yuv420p", "width": 832, "height": 480,
                "r_frame_rate": "not-a-rate", "avg_frame_rate": "0/0", "nb_frames": "81",
                "time_base": "1/16000", "start_pts": 0, "start_time": "0.000",
                "duration": "5.0625",
            },
            {
                "index": 1, "codec_type": "audio", "codec_name": "aac",
                "sample_rate": "48000", "channels": 2, "channel_layout": "stereo",
                "time_base": "1/48000", "start_pts": 0, "start_time": "0.000",
                "duration": "5.0625",
            },
        ],
        "format": {"duration": "5.0625"},
    }
    monkeypatch.setattr(
        "app.services.media_probe.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
    )
    result = probe_media("dummy.mp4")
    assert result["fps"] is None
    assert result["videoStreams"][0]["nb_frames"] == 81
    assert result["videoStreams"][0]["time_base"] == "1/16000"
    assert result["audioStreams"][0]["sample_rate"] == 48000
    assert result["audioStreams"][0]["channels"] == 2
    assert result["audioStreams"][0]["channel_layout"] == "stereo"
    assert result["videoStreams"][0]["codec_name"] == "h264"
    assert result["videoStreams"][0]["pix_fmt"] == "yuv420p"


def test_timeline_map_and_sample_frame_conversions_are_deterministic():
    windows = [
        {"start": 0.5, "duration": 2.0},
        {"start": 0.25, "duration": 3.0},
    ]
    timeline = _build_timeline_map(windows, fps=25, transition_frames=2)
    assert timeline[0]["outputStartFrame"] == 0
    assert timeline[1]["outputStartFrame"] == 48
    assert frames_to_samples(25, fps=25, sample_rate=48000) == 48000
    assert samples_to_frames(48000, sample_rate=48000, fps=25) == 25


def test_timeline_map_adds_rife_frames_and_xfade_overlaps():
    windows = [{"start": 0, "duration": 2}, {"start": 0, "duration": 3}]
    rife = _build_timeline_map(windows, fps=25, transition_frame_counts=[4])
    assert rife[1]["outputStartFrame"] == 54
    assert rife[1]["transitionBeforeFrames"] == 4
    xfade = _build_timeline_map(windows, fps=25, overlap_frames=2)
    assert xfade[1]["outputStartFrame"] == 48


def test_build_timeline_uses_pcm_48k_and_rejects_overlap():
    timeline = build_timeline(
        [{"text": "hello", "startFrame": 0, "endFrame": 25}],
        fps=25,
    )
    assert timeline.sample_rate == 48000
    assert timeline.items[0].end_sample == 48000
    with pytest.raises(ValueError, match="overlap"):
        build_timeline(
            [
                {"text": "a", "startFrame": 0, "endFrame": 25},
                {"text": "b", "startFrame": 24, "endFrame": 30},
            ],
            fps=25,
        )


def test_frontend_dialogues_map_shots_split_lines_and_voice_ids():
    from app.services.dubbing_timeline import build_dialogue_timeline

    timeline = build_dialogue_timeline(
        dialogues=[
            {
                "shotIndex": 1,
                "text": "周晴：第一句\n陆川: 第二句",
                "lipSyncPolicy": "preferred",
            }
        ],
        timeline_map=[
            {"segmentIndex": 0, "outputStartFrame": 0, "outputEndFrame": 50},
            {"segmentIndex": 1, "outputStartFrame": 48, "outputEndFrame": 98},
        ],
        characters=[
            {"id": "zhou", "name": "周晴", "voiceId": "voice-a"},
            {"id": "lu", "name": "陆川", "voiceId": "voice-b"},
        ],
        total_frames=120,
    )
    assert [(item.start_frame, item.end_frame) for item in timeline.items] == [(48, 73), (73, 98)]
    assert [item.text for item in timeline.items] == ["第一句", "第二句"]
    assert [item.voice_id for item in timeline.items] == ["voice-a", "voice-b"]
    assert timeline.duration_samples == 120 * 1920


def test_timeline_map_seconds_are_rebased_to_25fps_master():
    from app.services.dubbing_timeline import build_dialogue_timeline

    timeline = build_dialogue_timeline(
        dialogues=[{"shotIndex": 0, "text": "line", "lipSyncPolicy": "off"}],
        timeline_map=[
            {
                "segmentIndex": 0,
                "outputStartFrame": 16,
                "outputEndFrame": 32,
                "outputStartSec": 1.0,
                "outputEndSec": 2.0,
            }
        ],
        characters=[],
        total_frames=75,
        fps=25,
    )
    assert (timeline.items[0].start_frame, timeline.items[0].end_frame) == (25, 50)


def test_xfade_shot_slots_do_not_overlap_dialogue_audio():
    from app.services.dubbing_timeline import build_dialogue_timeline

    timeline = build_dialogue_timeline(
        dialogues=[
            {"shotIndex": 0, "text": "first"},
            {"shotIndex": 1, "text": "second"},
        ],
        timeline_map=[
            {"segmentIndex": 0, "outputStartFrame": 0, "outputEndFrame": 50},
            {"segmentIndex": 1, "outputStartFrame": 48, "outputEndFrame": 98},
        ],
        characters=[],
        total_frames=98,
    )
    assert [(item.start_frame, item.end_frame) for item in timeline.items] == [(0, 48), (48, 98)]


def test_legacy_timeline_can_be_padded_to_visual_master_length():
    timeline = build_timeline(
        [{"text": "hello", "startFrame": 0, "endFrame": 25}],
        fps=25,
        total_frames=100,
    )
    assert timeline.duration_samples == 100 * 1920


@pytest.mark.asyncio
async def test_pcm_mix_pads_tail_to_master_frame_count(tmp_path: Path):
    import subprocess
    from app.services.audio_mix import mix_pcm

    clip = tmp_path / "line.wav"
    made = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=d=1:r=48000", "-c:a", "pcm_s16le", str(clip)],
        capture_output=True,
        text=True,
    )
    assert made.returncode == 0
    timeline = build_timeline(
        [{"text": "x", "startFrame": 0, "endFrame": 25}],
        total_frames=50,
    )
    output = tmp_path / "mix.wav"
    await mix_pcm([clip], timeline, output)
    assert probe_media(output)["duration"] == pytest.approx(2.0, abs=0.001)


def test_required_tts_provider_fails_when_unconfigured():
    settings = Settings(tts_provider_mode="required", cosyvoice_url=None, cosyvoice_cli=None)
    with pytest.raises(ProviderUnavailable):
        create_tts_provider(settings)


def test_preferred_tts_provider_explicitly_degrades_when_unconfigured():
    settings = Settings(tts_provider_mode="preferred", cosyvoice_url=None, cosyvoice_cli=None)
    provider = create_tts_provider(settings)
    assert provider.degraded is True
    assert provider.name == "silence-fallback"


@pytest.mark.asyncio
async def test_visual_master_ffmpeg_fallback_is_explicit(monkeypatch, tmp_path: Path):
    from app.services import visual_master

    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "master.mp4"
    monkeypatch.setattr(visual_master, "_try_comfy_rife", lambda *a, **k: False)
    monkeypatch.setattr(
        visual_master,
        "probe_media",
        lambda _: {"duration": 5.0, "fps": 16.0, "videoStreams": [], "audioStreams": []},
    )

    async def fake_run(args):
        assert "-vsync" in args or "-fps_mode" in args
        assert "setpts=PTS-STARTPTS" in " ".join(args)
        output.write_bytes(b"master")

    monkeypatch.setattr(visual_master, "_run", fake_run)
    result = await visual_master.create_visual_master(source, output, settings=Settings())
    assert result["fps"] == 25
    assert result["degraded"] is True
    assert result["method"] == "ffmpeg-cfr-fallback"


@pytest.mark.asyncio
async def test_fit_audio_pads_short_audio_without_slowing(monkeypatch, tmp_path: Path):
    from app.services import audio_fit

    probes = iter([{"duration": 0.5}, {"duration": 1.0}])
    monkeypatch.setattr(audio_fit, "probe_media", lambda _: next(probes))
    captured = {}

    class Process:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        return Process()

    monkeypatch.setattr(audio_fit.asyncio, "create_subprocess_exec", fake_exec)
    await audio_fit.fit_audio(tmp_path / "in.wav", tmp_path / "out.wav", target_samples=48000)
    command = " ".join(captured["args"])
    assert "atempo" not in command
    assert "apad" in command


@pytest.mark.asyncio
async def test_fit_audio_rejects_more_than_five_percent_speedup(monkeypatch, tmp_path: Path):
    from app.services import audio_fit

    monkeypatch.setattr(audio_fit, "probe_media", lambda _: {"duration": 1.051})
    with pytest.raises(RuntimeError, match="5%"):
        await audio_fit.fit_audio(
            tmp_path / "in.wav", tmp_path / "out.wav", target_samples=48000
        )


@pytest.mark.asyncio
async def test_tts_rate_search_stays_within_cumulative_five_percent(monkeypatch, tmp_path: Path):
    from app.services import media_ops
    from app.services.dubbing_timeline import TimelineItem

    speeds = []

    class TTS:
        async def synthesize(self, item, output, *, speed=1.0):
            speeds.append(speed)

    item = TimelineItem(0, "短句", None, 0, 25, 0, 48000)
    durations = iter([1.03])
    monkeypatch.setattr(media_ops, "probe_media", lambda _: {"duration": next(durations)})

    async def fake_fit(source, output, **kwargs):
        assert kwargs["max_speedup"] == pytest.approx(1.05 / 1.03)
        return {"speed": 1.0, "mode": "pad"}

    monkeypatch.setattr(media_ops, "fit_audio", fake_fit)
    result = await media_ops._synthesize_and_fit(
        TTS(), item, tmp_path / "raw.wav", tmp_path / "fit.wav"
    )
    assert speeds == pytest.approx([1.0, 1.03])
    assert result["totalSpeed"] <= 1.05


@pytest.mark.asyncio
async def test_text_budget_rejects_clearly_impossible_dialogue(tmp_path: Path):
    from app.services import media_ops
    from app.services.dubbing_timeline import TimelineItem

    class TTS:
        async def synthesize(self, item, output, *, speed=1.0):
            raise AssertionError("TTS must not run after budget rejection")

    item = TimelineItem(0, "这" * 100, None, 0, 25, 0, 48000)
    with pytest.raises(RuntimeError, match="text budget"):
        await media_ops._synthesize_and_fit(
            TTS(), item, tmp_path / "raw.wav", tmp_path / "fit.wav"
        )


def test_dub_endpoint_runs_async_service(monkeypatch):
    async def fake_dub(body, settings=None):
        return {"path": "/tmp/dub.mp4", "degraded": False, "qa": {"ok": True}}

    monkeypatch.setattr("app.api.media.media_ops.dub_media", fake_dub)
    with TestClient(app) as client:
        response = client.post(
            "/v1/media/dub",
            json={
                "path": "/tmp/input.mp4",
                "segments": [{"text": "你好", "startFrame": 0, "endFrame": 25}],
            },
        )
    assert response.status_code == 200
    assert response.json()["qa"]["ok"] is True


def test_dub_endpoint_accepts_frontend_contract_and_returns_media(monkeypatch):
    async def fake_dub(body, settings=None):
        assert body["media"]["filename"] == "final.mp4"
        assert body["sampleRate"] == 48000
        return {
            "media": {
                "filename": "dubbed.mp4",
                "subfolder": "video",
                "type": "output",
                "path": "/tmp/dubbed.mp4",
            },
            "qa": {"ok": True},
        }

    monkeypatch.setattr("app.api.media.media_ops.dub_media", fake_dub)
    with TestClient(app) as client:
        response = client.post(
            "/v1/media/dub",
            json={
                "media": {"filename": "final.mp4", "subfolder": "video", "type": "output"},
                "splicePlan": {},
                "timelineMap": [
                    {"segmentIndex": 0, "outputStartFrame": 0, "outputEndFrame": 25}
                ],
                "characters": [{"id": "c1", "name": "周晴", "voiceId": "v1"}],
                "dialogues": [
                    {"shotIndex": 0, "shotName": "shot", "text": "周晴: 你好", "lipSyncPolicy": "off"}
                ],
                "fps": 25,
                "sampleRate": 48000,
            },
        )
    assert response.status_code == 200
    assert response.json()["media"]["filename"] == "dubbed.mp4"


@pytest.mark.asyncio
async def test_required_lipsync_blocks_degraded_visual_master(tmp_path: Path):
    from app.services.dubbing_timeline import build_timeline
    from app.services.lipsync import apply_selective_lipsync

    timeline = build_timeline(
        [{"text": "x", "startFrame": 0, "endFrame": 25, "lipSyncPolicy": "required"}],
        total_frames=25,
    )
    with pytest.raises(RuntimeError, match="degraded visual master"):
        await apply_selective_lipsync(
            tmp_path / "master.mp4",
            tmp_path / "audio.wav",
            tmp_path / "out.mp4",
            timeline=timeline,
            provider=None,
            visual_degraded=True,
        )


@pytest.mark.asyncio
async def test_selective_lipsync_extracts_16k_and_preserves_master_frames(tmp_path: Path):
    import shutil
    import subprocess
    from app.services.lipsync import apply_selective_lipsync

    master = tmp_path / "master.mp4"
    audio = tmp_path / "audio.wav"
    assert subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x180:d=2:r=25",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(master)],
        capture_output=True,
    ).returncode == 0
    assert subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=d=2:r=48000",
         "-c:a", "pcm_s16le", str(audio)],
        capture_output=True,
    ).returncode == 0
    timeline = build_timeline(
        [
            {"text": "off", "startFrame": 0, "endFrame": 25, "lipSyncPolicy": "off"},
            {"text": "sync", "startFrame": 25, "endFrame": 50, "lipSyncPolicy": "required"},
        ],
        total_frames=50,
    )

    class CopyProvider:
        degraded = False
        name = "test-provider"
        calls = 0

        async def apply(self, video, pcm16, output):
            self.calls += 1
            audio_probe = probe_media(pcm16)
            assert audio_probe["audioStreams"][0]["sample_rate"] == 16000
            assert audio_probe["audioStreams"][0]["channels"] == 1
            shutil.copyfile(video, output)

    provider = CopyProvider()
    output = tmp_path / "synced.mp4"
    result = await apply_selective_lipsync(
        master, audio, output, timeline=timeline, provider=provider, visual_degraded=False
    )
    assert provider.calls == 1
    assert result["appliedCount"] == 1
    assert probe_media(output)["videoStreams"][0]["nb_frames"] == 50


@pytest.mark.asyncio
async def test_preferred_lipsync_failure_is_explicit_fallback(tmp_path: Path):
    import subprocess
    from app.services.lipsync import apply_selective_lipsync

    master = tmp_path / "master.mp4"
    audio = tmp_path / "audio.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=s=160x90:d=1:r=25",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(master)],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=1",
         "-c:a", "pcm_s16le", str(audio)],
        capture_output=True,
        check=True,
    )
    timeline = build_timeline(
        [{"text": "x", "startFrame": 0, "endFrame": 25, "lipSyncPolicy": "preferred"}],
        total_frames=25,
    )

    class FailingProvider:
        degraded = False

        async def apply(self, video, pcm16, output):
            raise RuntimeError("provider failed")

    output = tmp_path / "fallback.mp4"
    result = await apply_selective_lipsync(
        master, audio, output, timeline=timeline, provider=FailingProvider(), visual_degraded=False
    )
    assert result["degraded"] is True
    assert "provider failed" in result["fallbacks"][0]["reason"]
    assert probe_media(output)["videoStreams"][0]["nb_frames"] == 25


@pytest.mark.asyncio
async def test_preferred_dub_pipeline_runs_with_explicit_fallbacks(tmp_path: Path):
    import subprocess
    from app.services.media_ops import dub_media

    root = tmp_path / "ComfyUI"
    (root / "output" / "video").mkdir(parents=True)
    (root / "input").mkdir(parents=True)
    source = root / "output" / "video" / "input.mp4"
    made = subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "color=c=blue:s=320x180:d=1:r=16",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
        ],
        capture_output=True,
        text=True,
    )
    assert made.returncode == 0, made.stderr[-400:]
    settings = Settings(
        comfyui_root=root,
        workflows_dir=tmp_path / "no-workflows",
        cosyvoice_url="",
        tts_provider_mode="preferred",
        latentsync_url="",
        lipsync_provider_mode="preferred",
        syncnet_qa_url="http://127.0.0.1:9/sync-qa",
    )
    result = await dub_media(
        {
            "path": str(source),
            "output": "dubbed.mp4",
            "segments": [{"text": "fallback", "startFrame": 0, "endFrame": 25}],
        },
        settings=settings,
    )
    assert result["degraded"] is True
    assert result["lipSync"]["appliedCount"] == 0
    assert result["qa"]["lipSyncQa"]["skipped"] is True
    assert {item["stage"] for item in result["degradations"]} == {
        "visualMaster", "tts", "lipsync"
    }
    assert result["qa"]["ok"] is True
    assert result["media"]["filename"] == "dubbed.mp4"
    assert result["qa"]["expectedFrames"] == 25
    assert abs(result["qa"]["decodedPcmSamples"] - 25 * 1920) <= 1920
