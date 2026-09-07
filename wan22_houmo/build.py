# Copyright (c) 2026 HOUMO AI
#
# File: build.py
# Description:
#   Wan2.2 HMM build tool. Compiles exported HMONNX components into HMM models.
#   Supports T5, VAE encode/decode, and high/low-noise DiT components.
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
from loguru import logger

from hmatc.exec.xh2_exec import Xh2Exec
from utils.common import find_hmonnx_file, first_not_none, get_model_configs, get_platform, get_parallel_jobs

HOUMO_TARGET = os.getenv("HOUMO_TARGET")
assert HOUMO_TARGET in ["xh2"], f"Unsupported HOUMO_TARGET: {HOUMO_TARGET}"

HOUMO_CORE_NUM = int(os.getenv("HOUMO_CORE_NUM", 2))
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
COMPONENTS = ("t5", "vae_encode", "vae_decode", "low_noise_model", "high_noise_model")


def get_args() -> argparse.Namespace:
    """Parse commandline."""
    parser = argparse.ArgumentParser()
    # fmt: off
    parser.add_argument("--config", dest="config_path", type=str, default=DEFAULT_CONFIG_PATH, help="path to config.yaml")
    parser.add_argument("--model_dir", dest="model_dir", type=str, default=None, help="path to the quantized model dir; defaults to output/<target>/hmquant_<model_size>")
    parser.add_argument("--model_name", dest="model_name", type=str, default=None, help="output houmo model name")
    parser.add_argument("--model_size", dest="model_size", type=str, default=None, help="output houmo model size")
    parser.add_argument("--output_dir", dest="output_dir", type=str, default=os.path.join("output", HOUMO_TARGET), help="build output dir")
    parser.add_argument("--component", dest="component", nargs="+", default=None, choices=COMPONENTS, help="components to build or test; defaults to all components")
    parser.add_argument("--j", dest="j", type=int, default=get_parallel_jobs(), help="build parallel jobs. Default is about 75%% of CPU count.")
    parser.add_argument("--ncore", dest="ncore", type=int, default=HOUMO_CORE_NUM, help="core number")
    parser.add_argument("--ndevice", dest="ndevice", type=int, default=None, help="device number")
    parser.add_argument("--enable_common_subgraph", dest="enable_common_subgraph", action="store_true", default=False, help="enable common subgraph optimization")
    parser.add_argument("--enable_xh2_stable_output", dest="enable_xh2_stable_output", action="store_true", default=False, help="enable stable output")
    parser.add_argument("--flash_attention", dest="flash_attention", type=int, default=2, help="flash attention optimization switches. First value is used by dit/text_encoder (0/1/2), second value is used by vae (0/1).")
    args = parser.parse_args()
    # fmt: on

    default_model_size, default_model_name, model_configs = get_model_configs(args.config_path)
    args.model_name = first_not_none(args.model_name, default_model_name)
    args.model_size = first_not_none(args.model_size, default_model_size)
    args.model_size = args.model_size.strip().lower()
    model_config = model_configs.get(args.model_name, {}).get(args.model_size, {})
    args.model_dir = first_not_none(args.model_dir, os.path.join("output", HOUMO_TARGET, f"hmquant_{args.model_size}"))
    args.ncore = first_not_none(args.ncore, model_config.get("ncore", HOUMO_CORE_NUM))
    args.ndevice = first_not_none(args.ndevice, model_config.get("ndevice", 1))

    return args


if __name__ == "__main__":
    args = get_args()
    logger.info(args)

    assert get_platform() == "x86_64", "Only supported for compilation on the x86_64 platform."

    model_specs = [
        {
            "name": "high_noise_model",
            "suffix": "high_noise",
            "build_kwargs": {
                "enable_common_subgraph": args.enable_common_subgraph,
            },
        },
        {
            "name": "low_noise_model",
            "suffix": "low_noise",
            "build_kwargs": {
                "enable_common_subgraph": args.enable_common_subgraph,
            },
        },
        {
            "name": "t5",
            "suffix": "t5",
            "build_kwargs": {},
        },
        {
            "name": "vae_decode",
            "suffix": "vae_decode",
            "build_kwargs": {},
        },
        {
            "name": "vae_encode",
            "suffix": "vae_encode",
            "build_kwargs": {},
        },
    ]

    for spec in model_specs:
        if args.component and spec["name"] not in args.component:
            continue
        if args.model_size == "t2v-a14b" and spec["name"] == "vae_encode":
            logger.info("Skip VAE encode compilation for T2V model_size=%s", args.model_size)
            continue
        model_dir = os.path.join(args.model_dir, spec["name"])
        build_kwargs = {
            "hmonnx": find_hmonnx_file(model_dir, pattern="*.onnx"),
            "hmm_name": f"{args.model_name}-{args.model_size}_{spec['suffix']}",
            "output": args.output_dir,
            "ncore": args.ncore,
            "ndevice": args.ndevice,
            "enable_xh2_stable_output": args.enable_xh2_stable_output,
            "flash_attn": args.flash_attention,
            "parallel_jobs": args.j,
            **spec["build_kwargs"],
        }
        logger.info(f"build hmonnx: {build_kwargs['hmonnx']}")
        Xh2Exec.build_from_hmonnx(**build_kwargs)

    logger.info(f"\n=== Build completed. ===")
