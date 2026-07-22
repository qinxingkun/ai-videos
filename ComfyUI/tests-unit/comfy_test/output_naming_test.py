import time

from comfy import output_naming


SAMPLE_T2V_PROMPT = {
    "37": {
        "class_type": "UNETLoader",
        "inputs": {"unet_name": "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors"},
    },
    "38": {
        "class_type": "UNETLoader",
        "inputs": {"unet_name": "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors"},
    },
}

SAMPLE_I2V_PROMPT = {
    **SAMPLE_T2V_PROMPT,
    "62": {
        "class_type": "LoadImage",
        "inputs": {"image": "my_cat_photo.png"},
    },
}


def test_build_t2v_prefix():
    ts = time.struct_time((2025, 6, 24, 15, 30, 0, 0, 0, 0))
    prefix = output_naming.build_media_filename_prefix(
        SAMPLE_T2V_PROMPT, "video/ComfyUI", now=ts
    )
    assert prefix.startswith("video/")
    assert "wan2.2_t2v_high_noise_14B_fp8_scaled" in prefix
    assert prefix.endswith("20250624-1530")
    assert "my_cat" not in prefix


def test_build_i2v_prefix_includes_image():
    ts = time.struct_time((2025, 6, 24, 9, 5, 0, 0, 0, 0))
    prefix = output_naming.build_media_filename_prefix(
        SAMPLE_I2V_PROMPT, "video/Wan2.2_i2v", now=ts
    )
    assert "my_cat_photo" in prefix
    assert prefix.endswith("20250624-0905")


def test_sanitize_removes_unsafe_chars():
    assert output_naming._sanitize_part("bad/name?.png") == "bad-name"
