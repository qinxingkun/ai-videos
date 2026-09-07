# Copyright (c) 2026 HOUMO AI
#
# File: wan2_2_merge_lora.py
# Description:
#   Merge task-specific Wan2.2 PEFT LoRA adapters into diffusion safetensors.
#
#   The script resolves the LoRA pair for each task and noise expert, applies
#   the adapters, and writes merged checkpoints under ``<model-dir>/merged``.
#   The resulting weights can be consumed by the Wan2.2 quantization exporter.
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

from __future__ import annotations

import argparse
import json
import re
import sys
import os
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WAN_REPO_DIR = os.path.join(SCRIPT_DIR, "Wan2.2-main")
if WAN_REPO_DIR not in sys.path:
    sys.path.insert(0, WAN_REPO_DIR)

import torch
from safetensors.torch import load_file, save_file

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xhmodel_merak.xh_other_model.models.wan2_2.wan2_2_converter import (  # noqa: E402
    Wan22ConvertConfig,
    Wan22Converter,
)
from wan.configs import WAN_CONFIGS  # noqa: E402
from wan.modules.model import WanModel  # noqa: E402

LORA_WEIGHT_RE = re.compile(r"^(?P<module>.+)\.lora_(?P<side>A|B|down|up)(?:\.[^.]+)?\.weight$")
PREFIXES = (
    "base_model.model.",
    "model.diffusion_model.",
    "diffusion_model.",
    "model.",
)


def parse_args() -> argparse.Namespace:
    # fmt: off
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--model-dir", required=True, help="Wan2.2 checkpoint directory.")
    parser.add_argument(
        "--lora-dir", action="append", default=None,
        help=(
            "LoRA adapter directory or safetensors file. Can be passed multiple times. "
            "When omitted, the task-specific LightX2V LoRA is selected from split_files/loras."
        ),
    )
    parser.add_argument(
        "--noise-model", choices=["low_noise_model", "high_noise_model"], action="append", default=None,
        help="Which diffusion model(s) to merge. Defaults to high_noise_model.",
    )
    parser.add_argument("--task", default="i2v-A14B")
    parser.add_argument("--output-dir", default=None, help="Defaults to <model-dir>/merged.")
    parser.add_argument("--output-dtype", choices=["keep", "float16", "bfloat16", "float32"], default="keep")
    parser.add_argument("--device", default="cuda:0", help="Used only when the base checkpoint is a directory.")
    parser.add_argument("--overwrite", action="store_true")
    # fmt: on
    return parser.parse_args()


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return data


def _load_adapter_tensors(adapter_path: Path) -> dict[str, torch.Tensor]:
    if adapter_path.is_file():
        return load_file(str(adapter_path), device="cpu")
    candidates = [adapter_path / "adapter_model.safetensors", adapter_path / "pytorch_lora_weights.safetensors"]
    for candidate in candidates:
        if candidate.is_file():
            return load_file(str(candidate), device="cpu")
    shards = sorted(adapter_path.glob("*.safetensors"))
    if len(shards) == 1:
        return load_file(str(shards[0]), device="cpu")
    raise FileNotFoundError(f"Cannot find a unique LoRA safetensors file in {adapter_path}")


def _strip_prefixes(module_path: str) -> str:
    module_path = module_path.replace(".base_layer", "")
    for prefix in PREFIXES:
        if module_path.startswith(prefix):
            return module_path[len(prefix) :]
    return module_path


def _find_target_key(base_state: dict[str, torch.Tensor], module_path: str) -> str:
    stripped = _strip_prefixes(module_path)
    candidates = [f"{stripped}.weight"]
    if stripped.startswith("module."):
        candidates.append(f"{stripped[len('module.'): ]}.weight")
    for key in candidates:
        if key in base_state:
            return key
    suffix = f".{stripped}.weight"
    matches = [key for key in base_state if key.endswith(suffix)]
    if len(matches) == 1:
        return matches[0]
    preview = ", ".join(matches[:5]) if matches else "no suffix matches"
    raise KeyError(f"Cannot resolve LoRA target module {module_path!r}; candidates: {preview}")


def _extract_lora_pairs(tensors: dict[str, torch.Tensor]) -> dict[str, dict[str, torch.Tensor]]:
    pairs: dict[str, dict[str, torch.Tensor]] = {}
    for key, tensor in tensors.items():
        match = LORA_WEIGHT_RE.match(key)
        if match is None:
            continue
        # pairs.setdefault(match.group("module"), {})[match.group("side")] = tensor
        side = match.group("side")
        side = {"down": "A", "up": "B"}.get(side, side)
        pairs.setdefault(match.group("module"), {})[side] = tensor
    if not pairs:
        raise ValueError("No LoRA A/B tensors found in adapter")
    incomplete = [module for module, sides in pairs.items() if set(sides) != {"A", "B"}]
    if incomplete:
        raise ValueError(f"Incomplete LoRA tensor pairs: {incomplete[:5]}")
    return pairs


def _orient_lora(a: torch.Tensor, b: torch.Tensor, base_shape: tuple[int, ...], module_path: str):
    if len(base_shape) != 2:
        raise ValueError(f"Only 2-D Linear weights are supported for {module_path}, got {base_shape}")
    out_dim, in_dim = base_shape
    if a.ndim != 2 or b.ndim != 2:
        raise ValueError(f"LoRA tensors must be 2-D for {module_path}, got {tuple(a.shape)} and {tuple(b.shape)}")
    if a.shape[1] == in_dim and b.shape[0] == out_dim and a.shape[0] == b.shape[1]:
        return a, b
    if a.shape[0] == in_dim and b.shape[1] == out_dim and a.shape[1] == b.shape[0]:
        return a.T.contiguous(), b.T.contiguous()
    raise ValueError(
        f"LoRA tensor shapes do not match base weight for {module_path}: "
        f"base={base_shape}, A={tuple(a.shape)}, B={tuple(b.shape)}"
    )


def _adapter_scale(adapter_path: Path, tensors: dict[str, torch.Tensor], module_path: str, rank: int) -> float:
    # ComfyUI LoRA stores alpha next to each module, while PEFT stores one
    # lora_alpha in adapter_config.json. Support both forms.
    alpha_tensor = tensors.get(f"{module_path}.alpha")
    if alpha_tensor is not None:
        alpha = float(alpha_tensor.detach().cpu().reshape(-1)[0].item())
    else:
        config_path = adapter_path / "adapter_config.json" if adapter_path.is_dir() else None
        if config_path is not None and config_path.is_file():
            config = _read_json(config_path)
            alpha = float(config.get("lora_alpha", rank))
        else:
            alpha = float(rank)
    return alpha / float(rank)


def _apply_adapter(base_state: dict[str, torch.Tensor], adapter_dir: Path) -> int:
    tensors = _load_adapter_tensors(adapter_dir)
    pairs = _extract_lora_pairs(tensors)
    merged = 0
    for module_path, sides in sorted(pairs.items()):
        target_key = _find_target_key(base_state, module_path)
        base_weight = base_state[target_key]
        a, b = _orient_lora(sides["A"], sides["B"], tuple(base_weight.shape), module_path)
        rank = int(a.shape[0])
        scale = _adapter_scale(adapter_dir, tensors, module_path, rank)
        delta = torch.matmul(b.float(), a.float()).mul_(scale)
        base_state[target_key] = (base_weight.float() + delta).to(base_weight.dtype)
        merged += 1
    return merged


def _task_lora_prefix(task: str) -> str:
    """Return the filename prefix used by the packaged LightX2V adapters."""
    task_name = task.lower().replace("-", "_")
    if task_name.startswith("i2v"):
        return "wan2.2_i2v_lightx2v_4steps_lora_v1_"
    if task_name.startswith("t2v"):
        return "wan2.2_t2v_lightx2v_4steps_lora_v1.1_"
    raise ValueError(f"No packaged 4-step LoRA mapping for task {task!r}; supported task families are i2v and t2v")


def _resolve_task_lora(model_dir: Path, task: str, noise_model: str) -> Path:
    lora_dir = model_dir / "split_files" / "loras"
    if not lora_dir.is_dir():
        raise FileNotFoundError(f"LoRA directory does not exist: {lora_dir}")
    prefix = _task_lora_prefix(task)
    role = "high_noise" if noise_model == "high_noise_model" else "low_noise"
    candidates = sorted(path for path in lora_dir.glob(f"{prefix}*.safetensors") if role in path.name)
    if not candidates:
        raise FileNotFoundError(
            f"Cannot find task-specific LoRA for task={task!r}, noise_model={noise_model!r} under {lora_dir}"
        )
    if len(candidates) > 1:
        raise RuntimeError(
            f"Multiple task-specific LoRAs matched task={task!r}, noise_model={noise_model!r}: "
            + ", ".join(str(path) for path in candidates)
        )
    return candidates[0]


def _convert_output_dtype(state: dict[str, torch.Tensor], dtype_name: str) -> dict[str, torch.Tensor]:
    if dtype_name == "keep":
        return state
    dtype = getattr(torch, dtype_name)
    return {key: value.to(dtype) if torch.is_floating_point(value) else value for key, value in state.items()}


def _resolve_unmerged_noise_model_path(model_dir: Path, task: str, noise_model: str) -> Path:
    """Resolve the base checkpoint for the requested task and noise role.

    The packaged ``split_files/diffusion_models`` directory contains both I2V
    and T2V checkpoints with the same ``low_noise``/``high_noise`` role.  A
    role-only sorted lookup can therefore silently select the I2V checkpoint
    for a T2V merge.  Match the task family in the filename first, mirroring
    the task-specific LoRA selection above.
    """
    cfg = WAN_CONFIGS[task]
    if noise_model == "low_noise_model":
        subfolder = cfg.low_noise_checkpoint
        role = "low_noise"
    else:
        subfolder = cfg.high_noise_checkpoint
        role = "high_noise"

    task_name = task.lower().replace("-", "_")
    if task_name.startswith("i2v"):
        task_family = "i2v"
    elif task_name.startswith("t2v"):
        task_family = "t2v"
    else:
        raise ValueError(
            f"Cannot resolve task-specific diffusion checkpoint for task {task!r}; "
            "supported task families are i2v and t2v"
        )

    split_dir = model_dir / "split_files" / "diffusion_models"
    if split_dir.is_dir():
        task_prefix = f"wan2.2_{task_family}_"
        split_candidates = sorted(
            path
            for path in split_dir.iterdir()
            if path.suffix == ".safetensors" and path.name.startswith(task_prefix) and role in path.name
        )
        if split_candidates:
            if len(split_candidates) > 1:
                raise RuntimeError(
                    f"Multiple {task} {noise_model} base checkpoints matched under {split_dir}: "
                    + ", ".join(str(path) for path in split_candidates)
                )
            return split_candidates[0]
    return model_dir / subfolder


def _load_base_state(model_dir: Path, task: str, device: torch.device, noise_model: str):
    source_path = _resolve_unmerged_noise_model_path(model_dir, task, noise_model)
    if source_path.is_file():
        return load_file(str(source_path), device="cpu"), source_path
    if not source_path.is_dir():
        raise FileNotFoundError(f"Cannot find base {noise_model} checkpoint: {source_path}")
    model = WanModel.from_pretrained(str(model_dir), subfolder=source_path.name)
    model.eval().requires_grad_(False).to(torch.float16).to(device)
    return {key: value.detach().cpu() for key, value in model.state_dict().items()}, source_path


def main() -> None:
    args = parse_args()
    model_dir = Path(args.model_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else model_dir / "merged"
    output_dir.mkdir(parents=True, exist_ok=True)
    noise_models = args.noise_model or ["high_noise_model"]
    explicit_lora_paths = [Path(path).expanduser().resolve() for path in args.lora_dir] if args.lora_dir else None

    Wan22Converter(str(model_dir), Wan22ConvertConfig(task=args.task, use_resolved_float_loader=True))
    device = torch.device(args.device)
    for noise_model in noise_models:
        base_state, source_path = _load_base_state(model_dir, args.task, device, noise_model)
        lora_paths = explicit_lora_paths or [_resolve_task_lora(model_dir, args.task, noise_model)]
        total_pairs = 0
        for adapter_path in lora_paths:
            total_pairs += _apply_adapter(base_state, adapter_path)
        base_state = _convert_output_dtype(base_state, args.output_dtype)

        adapter_tag = "_".join(path.stem for path in lora_paths)
        output_file = output_dir / f"wan2_2_{noise_model}_{adapter_tag}_merged.safetensors"
        if output_file.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists, pass --overwrite to replace: {output_file}")
        save_file(base_state, str(output_file), metadata={"format": "pt", "source": str(source_path)})
        print(f"Merged {total_pairs} LoRA target(s) for {noise_model}: {output_file}")


if __name__ == "__main__":
    main()
