# Copyright (c) 2026 HOUMO AI
#
# File: ptq.py
# Description:
#   Wan2.2 PTQ and HMONNX export entry.
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

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MERGE_LORA_SCRIPT = os.path.join(SCRIPT_DIR, "wan2_2_merge_lora.py")
WAN_REPO_DIR = os.path.join(SCRIPT_DIR, "Wan2.2-main")

if WAN_REPO_DIR not in sys.path:
    sys.path.insert(0, WAN_REPO_DIR)

import torch

from xhmodel_merak.workflows import AutoWorkflow
from xhquant.api import get_root_logger
from utils.common import first_not_none, get_model_configs, find_configs_merak_dir

HOUMO_TARGET = os.getenv("HOUMO_TARGET")
assert HOUMO_TARGET in ["xh2"], f"Unsupported HOUMO_TARGET: {HOUMO_TARGET}"

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

WORKFLOW_CONFIGS = {
    "i2v-A14B": "i2v_A14B/wan2_2_i2v_A14B.yaml",
    "t2v-A14B": "t2v_A14B/wan2_2_t2v_A14B.yaml",
}
MODEL_SIZE_TASKS = {
    "i2v-a14b": "i2v-A14B",
    "t2v-a14b": "t2v-A14B",
}
COMPONENTS = ("t5", "vae_encode", "vae_decode", "low_noise_model", "high_noise_model")
NOISE_COMPONENTS = ("low_noise_model", "high_noise_model")


def task_from_model_size(model_size: str) -> str:
    """Map the public config model size to Wan's canonical task name."""

    normalized = model_size.strip().lower()
    try:
        return MODEL_SIZE_TASKS[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(MODEL_SIZE_TASKS))
        raise ValueError(f"Unsupported Wan2.2 model_size {model_size!r}; expected one of: {supported}") from exc


def get_default_model_dir(model_config: dict) -> str:
    """Resolve the local checkpoint directory from the first ModelScope repo."""

    repositories = model_config.get("modelscope_repo", [])
    if not repositories or not isinstance(repositories[0], str):
        raise ValueError("model configuration must define a non-empty modelscope_repo list")
    repository_name = repositories[0].rstrip("/").rsplit("/", maxsplit=1)[-1]
    if not repository_name:
        raise ValueError(f"invalid first modelscope_repo value: {repositories[0]!r}")
    return os.path.join(SCRIPT_DIR, repository_name)


def parse_args() -> argparse.Namespace:
    # fmt: off
    parser = argparse.ArgumentParser(
        description="Quantize and export Wan2.2 components",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", dest="config_path", type=str, default=DEFAULT_CONFIG_PATH, help="path to config.yaml")
    parser.add_argument("--model_name", type=str, default=None, help="model name")
    parser.add_argument("--model_size", type=str, default=None, help="model size")
    parser.add_argument("--model_dir", default=None, help="input hf model path")
    parser.add_argument("--output_dir", default=None, help="output directory; defaults to output/<target>/hmquant_<model_size>",)
    parser.add_argument("--component", nargs="+", choices=COMPONENTS)
    parser.add_argument("--img_size", nargs=2, type=int, metavar=("WIDTH", "HEIGHT"), help="video size in width height order")
    parser.add_argument("--frame_num", type=int)
    parser.add_argument("--sample_steps", type=int)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--seed", type=int, default=1024)
    parser.add_argument("--merge-lora", action=argparse.BooleanOptionalAction, default=True, help="merge task-specific LoRA checkpoints before PTQ; use --no-merge-lora to disable")
    parser.add_argument("--lora-overwrite", action="store_true", help="regenerate matching merged checkpoints even when they already exist")
    parser.add_argument("--dump_golden", action="store_true")
    parser.add_argument("--debug", action="store_true")
    # fmt: on
    args = parser.parse_args()
    default_model_size, default_model_name, model_configs = get_model_configs(args.config_path)
    args.model_name = first_not_none(args.model_name, default_model_name)
    args.model_size = first_not_none(args.model_size, default_model_size)
    model_config = model_configs.get(args.model_name, {}).get(args.model_size, {})
    if not model_config:
        raise ValueError(
            f"No model configuration found for model_name={args.model_name!r}, "
            f"model_size={args.model_size!r} in {args.config_path}"
        )
    args.model_dir = first_not_none(args.model_dir, get_default_model_dir(model_config))
    args.output_dir = first_not_none(
        args.output_dir, os.path.join("output", HOUMO_TARGET, f"hmquant_{args.model_size}")
    )
    args.task = task_from_model_size(args.model_size)
    return args


def find_workflow_config(task: str) -> str:
    try:
        workflow_name = WORKFLOW_CONFIGS[task]
    except KeyError as exc:
        raise ValueError(f"Unsupported Wan2.2 task: {task!r}") from exc

    workflow_path = find_configs_merak_dir() / "workflows" / "xh2a" / "other_models" / "wan2_2" / workflow_name
    if not workflow_path.is_file():
        raise FileNotFoundError(f"Wan2.2 workflow config not found: {workflow_path}")
    return str(workflow_path)


def build_config_overrides(args: argparse.Namespace) -> dict[str, object]:
    overrides: dict[str, object] = {}
    overrides["export.wan2_2.quant_types.low_noise_model"] = "w8a8_ssfp"
    overrides["export.wan2_2.use_resolved_float_loader"] = True

    if args.component is not None:
        overrides["export.wan2_2.components"] = args.component
    if args.img_size is not None:
        overrides["export.wan2_2.size"] = args.img_size
    if args.frame_num is not None:
        overrides["export.wan2_2.frame_num"] = args.frame_num
    if args.sample_steps is not None:
        overrides["export.wan2_2.sample_steps"] = args.sample_steps

    return overrides


def _task_lora_prefix(task: str) -> str:
    task_name = task.lower().replace("-", "_")
    if task_name.startswith("i2v"):
        return "wan2.2_i2v_lightx2v_4steps_lora_v1_"
    if task_name.startswith("t2v"):
        return "wan2.2_t2v_lightx2v_4steps_lora_v1.1_"
    raise ValueError(f"No packaged LoRA mapping for task {task!r}")


def _resolve_task_lora(model_dir: Path, task: str, noise_model: str) -> Path:
    lora_root = model_dir / "split_files" / "loras"
    prefix = _task_lora_prefix(task)
    role = "high_noise" if noise_model == "high_noise_model" else "low_noise"
    candidates = sorted(path for path in lora_root.glob(f"{prefix}*.safetensors") if role in path.name)
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"Expected one LoRA for task={task}, component={noise_model} under "
            f"{lora_root}, got {[str(path) for path in candidates]}"
        )
    return candidates[0]


def _selected_noise_models(args: argparse.Namespace) -> tuple[str, ...]:
    if args.component is None:
        return NOISE_COMPONENTS
    requested = set(args.component)
    return tuple(component for component in NOISE_COMPONENTS if component in requested)


def _expected_merged_file(
    output_dir: Path,
    noise_model: str,
    lora_paths: list[Path],
) -> Path:
    adapter_tag = "_".join(path.stem for path in lora_paths)
    return output_dir / f"wan2_2_{noise_model}_{adapter_tag}_merged.safetensors"


def merge_lora_weights(args: argparse.Namespace, logger) -> tuple[Path, ...]:
    """Merge the selected DiT LoRAs in an isolated process before PTQ."""

    noise_models = _selected_noise_models(args)
    if not args.merge_lora:
        logger.info("LoRA merge is disabled by --no-merge-lora")
        return ()
    if not noise_models:
        logger.info("Skip LoRA merge because no DiT component is selected")
        return ()

    model_dir = Path(args.model_dir).expanduser().resolve()
    merge_script = Path(MERGE_LORA_SCRIPT).resolve()
    if not merge_script.is_file():
        raise FileNotFoundError(f"Wan2.2 LoRA merge script not found: {merge_script}")

    output_dir = model_dir / "merged"
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_files: dict[str, Path] = {}
    missing_models: list[str] = []
    for noise_model in noise_models:
        lora_paths = [_resolve_task_lora(model_dir, args.task, noise_model)]
        expected_file = _expected_merged_file(output_dir, noise_model, lora_paths)
        expected_files[noise_model] = expected_file
        if args.lora_overwrite or not expected_file.is_file():
            missing_models.append(noise_model)
        else:
            logger.info(
                "Reuse merged LoRA checkpoint for %s: %s",
                noise_model,
                expected_file,
            )

    if missing_models:
        command = [
            sys.executable,
            str(merge_script),
            "--model-dir",
            str(model_dir),
            "--task",
            args.task,
            "--output-dir",
            str(output_dir),
        ]
        for noise_model in missing_models:
            command.extend(("--noise-model", noise_model))
        if args.lora_overwrite:
            command.append("--overwrite")

        logger.info(
            "Merge LoRA checkpoints before PTQ for components: %s",
            missing_models,
        )
        subprocess.run(command, check=True, cwd=SCRIPT_DIR)

    for noise_model, expected_file in expected_files.items():
        if not expected_file.is_file():
            raise FileNotFoundError(f"LoRA merge did not produce {noise_model} checkpoint: {expected_file}")
        logger.info("PTQ will use merged %s checkpoint: %s", noise_model, expected_file)
    return tuple(expected_files[component] for component in noise_models)


def export_tokenizer_config(model_dir: str, output_dir: str, logger) -> Path:
    """Copy the bundled UMT5 tokenizer into the demo dependency directory."""

    source = Path(model_dir).expanduser().resolve() / "google" / "umt5-xxl"
    target = Path(output_dir).expanduser().resolve() / "hf_config"
    if not source.is_dir():
        raise FileNotFoundError(f"UMT5 tokenizer directory not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    logger.info("Copied tokenizer config: %s -> %s", source, target)
    return target


def main() -> None:
    args = parse_args()
    logger = get_root_logger()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if output_dir.exists():
        raise FileExistsError(
            f"Output directory already exists: {output_dir}. Remove it or choose a different directory."
        )
    logger.info("Using output directory: %s", output_dir)

    merge_lora_weights(args, logger)

    workflow_config = find_workflow_config(args.task)
    logger.info("Using workflow config: %s", workflow_config)
    workflow = AutoWorkflow.from_config(
        model_dir=os.path.abspath(args.model_dir),
        config_path=workflow_config,
        seed=args.seed,
        debug=args.debug,
    )
    overrides = build_config_overrides(args)
    output_dir = str(output_dir)

    quant_result = workflow.quant(
        output_dir=output_dir,
        device=args.device,
        config_overrides=overrides,
    )
    export_result = workflow.export(
        quant_result=quant_result,
        output_dir=output_dir,
        device=args.device,
        config_overrides=overrides,
    )
    if args.dump_golden:
        golden_meta = workflow.dump_golden(export_result=export_result, device=args.device)
        logger.info("Golden metadata: %s", golden_meta)
    export_tokenizer_config(args.model_dir, output_dir, logger)


if __name__ == "__main__":
    main()
