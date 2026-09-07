# Copyright (c) 2026 HOUMO AI
#
# File: get_model.py
# Description:
#   Download Wan2.2 model assets and checkpoints according to config.yaml.
#   Resolves the selected task/model size and retrieves files for HMM,
#   quantization, compilation, or inference workflows.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import os
import argparse
import shutil
from pathlib import Path

from utils.common import get_houmo_version, get_model_configs, first_not_none
from utils.download import hmatc_get_file

HOUMO_TARGET = os.getenv("HOUMO_TARGET")
assert HOUMO_TARGET in ["xh2"], f"Unsupported HOUMO_TARGET: {HOUMO_TARGET}"
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def get_args() -> argparse.Namespace:
    """Parse commandline."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        dest="config_path",
        type=str,
        default=DEFAULT_CONFIG_PATH,
        help="path to config.yaml",
    )
    parser.add_argument(
        "--type",
        dest="file_type",
        type=str,
        default="hmm",
        choices=["raw", "hmm"],
        help="which resource to get, choice in [raw, hmm]",
    )
    parser.add_argument(
        "--download_dir",
        dest="download_dir",
        type=str,
        default=".",
        help="where to save downloaded model",
    )
    parser.add_argument(
        "--extract_dir",
        dest="extract_dir",
        type=str,
        default=None,
        help="where to save extracted files",
    )
    parser.add_argument(
        "--source_type",
        dest="source_type",
        type=str,
        default="jfrog",
        choices=["jfrog", "modelscope"],
        help="download the model from which source",
    )
    parser.add_argument(
        "--model_name",
        dest="model_name",
        type=str,
        default=None,
        help="model name",
    )
    parser.add_argument(
        "--model_size",
        dest="model_size",
        type=str,
        default=None,
        help="model size",
    )
    parser.add_argument(
        "--ndevice",
        dest="ndevice",
        type=int,
        default=None,
        help="device number",
    )
    parser.add_argument(
        "--ncore",
        dest="ncore",
        type=int,
        default=None,
        help="number of cores",
    )
    parser.add_argument(
        "--quant_type",
        dest="quant_type",
        type=str,
        default=None,
        help="quantization type",
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = get_args()

    default_model_size, default_model_name, model_configs = get_model_configs(args.config_path)

    model_name = first_not_none(args.model_name, default_model_name)
    model_size = first_not_none(args.model_size, default_model_size)
    model_config = model_configs.get(model_name, {}).get(model_size, {})

    ndevice = first_not_none(args.ndevice, model_config.get("ndevice", 1))
    ncore = first_not_none(args.ncore, model_config.get("ncore", 2))
    quant_type = first_not_none(args.quant_type, model_config.get("quant_type", "w8a8"))
    video_width = model_config.get("video_width")
    video_height = model_config.get("video_height")
    hmm_suffix = ""
    if video_width is not None and video_height is not None:
        hmm_suffix = f"{video_width}x{video_height}"

    model_cfgs = {
        "target": HOUMO_TARGET,
        "version": get_houmo_version(),
        "model_type": "llm",
        "model_name": model_name,
        "model_info": {
            "model_size": model_size,
            "hmm_suffix": hmm_suffix,
            "ncore": ncore,
            "ndevice": ndevice,
            "batch": 1,
            "quant_type": quant_type,
        },
        "default_files": ["models/raw/other/wan2.2_source_code_20260730.zip"],
        "modelscope_repo": {
            "repo_ids": model_config.get("modelscope_repo", []),
            "ignore_patterns": [
                "*_bf16*.safetensors",
                "*_fp8_scaled*.safetensors",
                "*_int8*.safetensors",
                "*animate*",
                "*s2v*",
                "*ti2v*",
                "*fun_*",
                "*chrono*",
                "*.pth",
                "*diffusion_pytorch_model*",
            ],
        },
    }

    if args.file_type == "hmm":
        del model_cfgs["modelscope_repo"]

    _, ret_dict = hmatc_get_file(
        model_cfgs,
        args.file_type,
        args.download_dir,
        args.extract_dir,
        args.source_type,
    )
    if ret_dict.get("ret", False) is False:
        exit(1)

    if args.file_type == "raw":
        root = Path(args.download_dir).expanduser().resolve()
        repo_ids = model_config.get("modelscope_repo", [])
        if len(repo_ids) < 2 or not all(isinstance(repo_id, str) and repo_id.strip() for repo_id in repo_ids):
            raise ValueError(
                f"model configuration for {model_name}-{model_size} must define at least two valid "
                "modelscope_repo entries to copy tokenizer files"
            )
        source_repo = repo_ids[-1].rstrip("/").rsplit("/", maxsplit=1)[-1]
        target_repo = repo_ids[0].rstrip("/").rsplit("/", maxsplit=1)[-1]
        source = root / source_repo / "google"
        target = root / target_repo / "google"
        if not source.is_dir():
            raise FileNotFoundError(f"downloaded tokenizer directory not found for {model_size}: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, dirs_exist_ok=True)
        print(f"Copied tokenizer directory: {source} -> {target}", flush=True)
