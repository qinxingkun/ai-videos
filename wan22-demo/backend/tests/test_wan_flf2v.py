from __future__ import annotations

from pathlib import Path

from app.services.workflow_builder import build_wan_flf2v, load_workflow

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows" / "flf2v.api.json"


def test_build_wan_flf2v_injects_prompt_and_images():
    if not WORKFLOW.exists():
        return
    base = load_workflow(WORKFLOW)
    built = build_wan_flf2v(
        base,
        {
            "positivePrompt": "hero walks forward",
            "negativePrompt": "blur",
            "width": 1280,
            "height": 720,
            "length": 81,
            "seed": 99,
            "firstImageName": "start.png",
            "lastImageName": "end.png",
            "filenamePrefix": "video/wan2.2_flf2v_test",
        },
    )
    g = built["graph"]
    assert g["6"]["inputs"]["text"] == "hero walks forward"
    assert g["7"]["inputs"]["text"] == "blur"
    assert g["62"]["inputs"]["image"] == "start.png"
    assert g["64"]["inputs"]["image"] == "end.png"
    assert g["63"]["class_type"] == "WanFirstLastFrameToVideo"
    assert g["63"]["inputs"]["length"] == 81
    assert g["3"]["inputs"]["noise_seed"] == 99
