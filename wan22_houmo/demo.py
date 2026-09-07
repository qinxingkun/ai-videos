# Copyright (c) 2026 HOUMO AI
#
# File: demo.py
# Description:
#   Run Wan2.2 T2V/I2V inference with precompiled HMM components through
#   tcim_lite. Host-side tokenization, frontends, sampling, and video output
#   are handled in Python while T5, VAE, and DiT execute on HOUMO devices.
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
import gc
import importlib.machinery
import math
import os
import re
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from tqdm import tqdm

from houmo_engine.perf import PerfTracker
import tcim_lite as tcim

SCRIPT_DIR = Path(__file__).resolve().parent
WAN_REPO_DIR = SCRIPT_DIR / "Wan2.2-main"
if str(WAN_REPO_DIR) not in sys.path:
    sys.path.insert(0, str(WAN_REPO_DIR))

# Import only the upstream modules required by the lightweight pipeline.
for package_name, package_path in (
    ("wan", WAN_REPO_DIR / "wan"),
    ("wan.modules", WAN_REPO_DIR / "wan" / "modules"),
    ("wan.utils", WAN_REPO_DIR / "wan" / "utils"),
):
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_path)]
        package.__package__ = package_name
        package.__spec__ = importlib.machinery.ModuleSpec(package_name, loader=None, is_package=True)
        sys.modules[package_name] = package

from wan.configs import WAN_CONFIGS  # noqa: E402
from wan.modules.tokenizers import HuggingfaceTokenizer  # noqa: E402
from wan.utils.fm_solvers import (  # noqa: E402
    FlowDPMSolverMultistepScheduler,
    get_sampling_sigmas,
    retrieve_timesteps,
)
from wan.utils.fm_solvers_unipc import FlowUniPCMultistepScheduler  # noqa: E402
from hmatc.utils.utils import first_not_none, get_model_configs

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO")


HOUMO_TARGET = os.getenv("HOUMO_TARGET")
assert HOUMO_TARGET in ["xh2"], f"Unsupported HOUMO_TARGET: {HOUMO_TARGET}"

HOUMO_EXAMPLES_PATH = Path(os.getenv("HOUMO_EXAMPLES_PATH", str(SCRIPT_DIR.parents[3])))

DEFAULT_CONFIG_PATH = SCRIPT_DIR / "config.yaml"
DEFAULT_I2V_IMAGE = HOUMO_EXAMPLES_PATH / "data" / "pic" / "wan2.2_i2v_input_harvest.jpg"
MODEL_SIZE_TASKS = {"i2v-a14b": "i2v-A14B", "t2v-a14b": "t2v-A14B"}
PERF_ROOT = "wan2_2"

DEFAULT_PROMPT_I2V = "镜头缓慢向前推进，保持电影级运镜。村民们自然地忙碌着：前景男子不断挥动铁锹将麦粒装进麻袋，动作连贯有力；旁边妇女双手扶着麻袋，随着麦粒逐渐装满不断调整姿势。背景中脱粒机持续运转，麦秸不断送入机器，扬起细微的灰尘。另一侧几位村民挥动木耙翻晒粮食，动作节奏自然。微风吹动树叶、衣角和地上的麦秸，空气中漂浮着细小灰尘。远处一辆农用三轮车缓缓驶过，轮胎扬起轻微尘土。阳光穿过树叶形成轻微变化的光影，整个画面真实自然，人物身份保持一致，无人物跳变，无物体闪烁，90年代豫东农村纪实电影风格，5秒。"
DEFAULT_PROMPT_T2V = "水下超现实场景，一只巨大的半透明水母在深邃的蓝色海洋中优雅地收缩伞状体，其触手如丝带般轻柔地飘动缠绕。光线穿过水面形成丁达尔效应，照亮水母体内的生物荧光。水母游动时，周围微小的浮游生物像星点一样散开，画面带有梦幻、迷幻的氛围，水下摄影风格，高清晰度，5秒钟。"


def parse_args() -> argparse.Namespace:
    # fmt: off
    parser = argparse.ArgumentParser(
        description="Run Wan2.2 HMM components.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--config", dest="config_path", default=str(DEFAULT_CONFIG_PATH), help="path to config.yaml")
    parser.add_argument("--model_name", default=None, help="model name in config.yaml")
    parser.add_argument("--model_size", default=None, help="model size in config.yaml")
    parser.add_argument("--t5-hmm", default=None, help="compiled T5 HMM path; derived from model_name/model_size when omitted")
    parser.add_argument("--vae-decode-hmm", default=None, help="compiled VAE decoder HMM path; derived when omitted")
    parser.add_argument("--low-noise-hmm", default=None, help="compiled low-noise DiT HMM path; derived when omitted")
    parser.add_argument("--high-noise-hmm", default=None, help="compiled high-noise DiT HMM path; derived when omitted")
    parser.add_argument("--vae-encode-hmm", default=None, help="VAE encoder HMM; required only for i2v")
    parser.add_argument("--t5-frontend", default=None, help="exported T5 token embedding PT")
    parser.add_argument("--low-noise-frontend", default=None, help="exported low-noise timestep frontend PT")
    parser.add_argument("--high-noise-frontend", default=None, help="exported high-noise timestep frontend PT")
    parser.add_argument("--tokenizer-path", default=None, help="T5 tokenizer directory; derived from the first modelscope_repo when omitted")
    parser.add_argument("--prompt", default=None, help="positive text prompt; uses the task default when omitted")
    parser.add_argument("--negative-prompt", default="", help="negative text prompt; uses the model default when empty")
    parser.add_argument("--image", default=str(DEFAULT_I2V_IMAGE), help="I2V input image path; ignored for T2V")
    parser.add_argument("--output", default=None, help="output video path; defaults to wan2.2-<model_size>_demo.mp4")
    parser.add_argument("--size", nargs=2, type=int, default=None, metavar=("WIDTH", "HEIGHT"), help="optional static output size consistency check")
    parser.add_argument("--frame-num", type=int, default=None, help="optional static frame-count consistency check")
    parser.add_argument("--sample-steps", type=int, default=4, help="number of diffusion sampling steps")
    parser.add_argument("--sample-shift", type=float, default=5.0, help="flow-matching noise schedule shift")
    parser.add_argument("--guide-scale", nargs="+", type=float, default=(1.0, 1.0), metavar=("LOW_NOISE", "HIGH_NOISE"), help="CFG scale for low/high-noise experts; one value applies to both")
    parser.add_argument("--boundary", type=float, default=None, help="normalized high/low expert boundary in [0, 1]")
    parser.add_argument("--sample-solver", choices=("euler","unipc", "dpm++"), default="euler", help="diffusion scheduler solver")
    parser.add_argument("--seed", type=int, default=0, help="random seed for latent initialization")
    parser.add_argument("--fps", type=int, default=16, help="output video frame rate")
    parser.add_argument("--t5-device", type=int, default=0, help="HOUMO device ID for the T5 HMM")
    parser.add_argument("--vae-encode-device", type=int, default=1, help="HOUMO device ID for the VAE encoder HMM")
    parser.add_argument("--vae-decode-device", type=int, default=1, help="HOUMO device ID for the VAE decoder HMM")
    parser.add_argument("--high-noise-device", type=int, default=0, help="HOUMO device ID for the high-noise DiT HMM")
    parser.add_argument("--low-noise-device", type=int, default=1, help="HOUMO device ID for the low-noise DiT HMM")
    # fmt: on

    args = parser.parse_args()
    default_model_size, default_model_name, model_configs = get_model_configs(args.config_path)
    args.model_name = first_not_none(args.model_name, default_model_name)
    args.model_size = first_not_none(args.model_size, default_model_size)
    args.model_size = args.model_size.strip().lower()
    model_config = model_configs.get(args.model_name, {}).get(args.model_size, {})
    if not model_config:
        raise ValueError(
            f"No model configuration found for model_name={args.model_name!r}, "
            f"model_size={args.model_size!r} in {args.config_path}"
        )
    derived_task = MODEL_SIZE_TASKS.get(args.model_size)
    if derived_task is None:
        raise ValueError(f"Unsupported Wan2.2 model_size: {args.model_size!r}")
    args.task = derived_task
    args.output = first_not_none(args.output, f"wan2.2-{args.model_size}_demo.mp4")

    hmm_dir = SCRIPT_DIR / "output" / HOUMO_TARGET
    hmquant_root = hmm_dir
    size_specific_hmquant_dir = hmquant_root / f"hmquant_{args.model_size}"
    legacy_hmquant_dir = hmquant_root / "hmquant"
    hmquant_dir = size_specific_hmquant_dir if size_specific_hmquant_dir.is_dir() else legacy_hmquant_dir

    model_prefix = f"{args.model_name}-{args.model_size}"
    args.t5_hmm = first_not_none(args.t5_hmm, hmm_dir / f"{model_prefix}_t5.hmm")
    args.vae_encode_hmm = first_not_none(args.vae_encode_hmm, hmm_dir / f"{model_prefix}_vae_encode.hmm")
    args.vae_decode_hmm = first_not_none(args.vae_decode_hmm, hmm_dir / f"{model_prefix}_vae_decode.hmm")
    args.low_noise_hmm = first_not_none(args.low_noise_hmm, hmm_dir / f"{model_prefix}_low_noise.hmm")
    args.high_noise_hmm = first_not_none(args.high_noise_hmm, hmm_dir / f"{model_prefix}_high_noise.hmm")
    args.t5_frontend = first_not_none(args.t5_frontend, hmquant_dir / "quant_embedding.pt")
    args.low_noise_frontend = first_not_none(args.low_noise_frontend, hmquant_dir / "low_noise_timestep_embedding.pt")
    args.high_noise_frontend = first_not_none(
        args.high_noise_frontend, hmquant_dir / "high_noise_timestep_embedding.pt"
    )
    args.tokenizer_path = first_not_none(args.tokenizer_path, hmquant_dir / "hf_config")

    return args


def _required_path(value: str, description: str, *, directory=False) -> Path:
    path = Path(value).expanduser().resolve()
    exists = path.is_dir() if directory else path.is_file()
    if not exists:
        kind = "directory" if directory else "file"
        raise FileNotFoundError(f"{description} {kind} not found: {path}")
    return path


def _to_numpy(value) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().contiguous().numpy()
    if isinstance(value, np.ndarray):
        return np.ascontiguousarray(value)
    return np.ascontiguousarray(np.asarray(value))


def _normalize_tensor_name(name: str) -> str:
    """Normalize common compiler suffixes without discarding semantic names."""

    return re.sub(r"(?:\.\d+|:\d+)$", "", name)


def _resize_with_letterbox(image: Image.Image, width: int, height: int) -> Image.Image:
    """Resize an image proportionally and center it on a black canvas.

    The HMM graphs use static spatial shapes, so letterboxing preserves the
    input geometry when the source and model aspect ratios differ.
    """

    image = image.convert("RGB")
    source_width, source_height = image.size
    if source_width <= 0 or source_height <= 0:
        raise ValueError(f"input image has invalid size: {image.size}")
    scale = min(width / source_width, height / source_height)
    resized_width = max(1, round(source_width * scale))
    resized_height = max(1, round(source_height * scale))
    resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), color=(0, 0, 0))
    offset = ((width - resized_width) // 2, (height - resized_height) // 2)
    canvas.paste(resized, offset)
    return canvas


@dataclass(frozen=True)
class TensorSpec:
    name: str
    shape: tuple[int, ...]
    dtype: object


class TcimRuntimeModel:
    """Small tcim_lite wrapper for one resident, stateless HMM component.

    PyTorch tensors remain on the host side and are converted to NumPy before
    being bound to the HMM. Outputs are copied back to host tensors after sync.
    """

    def __init__(
        self,
        name: str,
        model_path: Path,
        device_id: int,
        dev_manager,
        perf: PerfTracker,
    ):
        self.name = name
        self.device_id = device_id
        self.perf = perf

        with self.perf.scope(f"{PERF_ROOT}.{name}"):
            with self.perf.scope(f"{PERF_ROOT}.{name}.load"):
                self.weight_manager = tcim.runtime.WeightManager(dev_manager)
                self.option = tcim.runtime.Option(self.weight_manager)
                self.model = tcim.runtime.load(str(model_path), option=self.option)
                self.input_specs = tuple(self._read_input_spec(index) for index in range(self.model.get_num_inputs()))
                self.output_specs = tuple(
                    self._read_output_spec(index) for index in range(self.model.get_num_outputs())
                )
        normalized_names = [_normalize_tensor_name(spec.name) for spec in self.input_specs]
        if len(normalized_names) != len(set(normalized_names)):
            raise ValueError(
                f"{name} inputs are ambiguous after suffix normalization: "
                f"{[spec.name for spec in self.input_specs]}"
            )
        logger.info(f"[HMM] Loaded component={name} device={device_id} model={model_path}", flush=True)
        self.print_protocol()

    @property
    def input_shapes(self) -> dict[str, tuple[int, ...]]:
        return {_normalize_tensor_name(spec.name): spec.shape for spec in self.input_specs}

    def _read_input_spec(self, index: int) -> TensorSpec:
        name = self.model.get_input_name(index)
        info = self.model.get_input_info(name)
        return TensorSpec(name, tuple(int(dim) for dim in info.shape), info.dtype)

    def _read_output_spec(self, index: int) -> TensorSpec:
        name = self.model.get_output_name(index)
        info = self.model.get_output_info(name)
        return TensorSpec(name, tuple(int(dim) for dim in info.shape), info.dtype)

    def print_protocol(self):
        logger.debug(f"[HMM Protocol] component={self.name}", flush=True)
        for index, spec in enumerate(self.input_specs):
            logger.debug(
                f"  input[{index}] name={spec.name} shape={spec.shape} " f"dtype={spec.dtype}",
                flush=True,
            )
        for index, spec in enumerate(self.output_specs):
            logger.debug(
                f"  output[{index}] name={spec.name} shape={spec.shape} " f"dtype={spec.dtype}",
                flush=True,
            )

    def __call__(self, inputs: Mapping[str, object]):
        # Bind inputs by semantic names instead of relying on a fragile fixed
        # positional order; compiler-generated suffixes are normalized above.
        expected = {_normalize_tensor_name(spec.name): spec for spec in self.input_specs}
        if set(inputs) != set(expected):
            raise ValueError(f"{self.name} input names mismatch: " f"expected={list(expected)}, got={list(inputs)}")
        with self.perf.scope(f"{PERF_ROOT}.{self.name}.set_input"):
            for semantic_name, spec in expected.items():
                array = _to_numpy(inputs[semantic_name])
                if tuple(array.shape) != spec.shape:
                    raise ValueError(
                        f"{self.name}.{semantic_name} shape mismatch: " f"HMM={spec.shape}, input={tuple(array.shape)}"
                    )
                array = array.astype(spec.dtype, copy=False)
                self.model.set_input(spec.name, array)

        with self.perf.scope(f"{PERF_ROOT}.{self.name}.infer"):
            self.model.run()
            self.model.sync()
        # ``to_host`` is intentional: subsequent CFG and scheduler operations
        # are performed by Python/PyTorch on the host CPU.
        with self.perf.scope(f"{PERF_ROOT}.{self.name}.get_output"):
            outputs = []
            for spec in self.output_specs:
                output = self.model.get_dev_output(spec.name).to_host().numpy()
                outputs.append(torch.from_numpy(output))
        return outputs[0] if len(outputs) == 1 else tuple(outputs)

    def release(self):
        if self.model is None:
            return
        model = self.model
        option = self.option
        weight_manager = self.weight_manager
        self.model = None
        self.option = None
        self.weight_manager = None
        del model, option, weight_manager
        gc.collect()
        logger.debug(
            f"[HMM] Released component={self.name} device={self.device_id}",
            flush=True,
        )


def sinusoidal_embedding_1d(dim: int, position: torch.Tensor) -> torch.Tensor:
    if dim % 2:
        raise ValueError(f"sinusoidal embedding dimension must be even, got {dim}")
    half = dim // 2
    position = position.to(torch.float64)
    sinusoid = torch.outer(
        position,
        torch.pow(
            10000,
            -torch.arange(half, device=position.device).div(half),
        ),
    )
    return torch.cat([torch.cos(sinusoid), torch.sin(sinusoid)], dim=1)


def _load_pt_state(path: Path) -> dict[str, torch.Tensor]:
    state = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(state, dict) or not all(isinstance(value, torch.Tensor) for value in state.values()):
        raise TypeError(f"frontend PT must contain a tensor state dict: {path}")
    return state


def _load_token_embedding(path: Path, dtype: torch.dtype) -> nn.Embedding:
    state = _load_pt_state(path)
    weight = state.get("weight")
    if weight is None or weight.ndim != 2:
        raise ValueError(f"T5 token embedding must contain a 2D 'weight' tensor: {path}")
    return nn.Embedding.from_pretrained(weight.to(dtype=dtype), freeze=True)


class HmmT5:
    """Host token embedding plus the compiled T5 encoder HMM.

    Tokenization and the embedding lookup are outside the HMM graph. The HMM
    receives only ``inputs_embeds`` and the attention bias tensor.
    """

    def __init__(
        self,
        runtime: TcimRuntimeModel,
        frontend_file: Path,
        tokenizer_path: Path,
        device: torch.device,
        dtype=torch.float16,
    ):
        self.runtime = runtime
        self.device = device
        self.dtype = dtype
        self.perf = runtime.perf
        shapes = runtime.input_shapes
        embedding_shape = shapes.get("inputs_embeds")
        bias_shape = shapes.get("mask_bias")
        if embedding_shape is None or bias_shape is None:
            raise KeyError(f"T5 HMM must expose inputs_embeds and mask_bias: {shapes}")
        if len(embedding_shape) != 3 or len(bias_shape) != 4:
            raise ValueError(f"Unexpected T5 HMM input shapes: {shapes}")
        self.text_len = int(embedding_shape[1])
        if bias_shape[-1] != self.text_len:
            raise ValueError(f"T5 embedding/bias sequence mismatch: {shapes}")
        # Use the original T5 legacy/SentencePiece path explicitly. This avoids
        # Transformers' slow-to-fast conversion warnings and keeps tokenization
        # behavior aligned with the Wan2.2 source implementation.
        self.tokenizer = HuggingfaceTokenizer(
            name=str(tokenizer_path),
            seq_len=self.text_len,
            clean="whitespace",
            use_fast=False,
            legacy=True,
        )
        self.embedding = _load_token_embedding(frontend_file, dtype).to(device)
        if self.embedding.embedding_dim != embedding_shape[-1]:
            raise ValueError(
                f"T5 embedding width mismatch: HMM={embedding_shape[-1]}, " f"frontend={self.embedding.embedding_dim}"
            )

    def _validate_text_lengths(self, texts: Sequence[str], prompt_name: str) -> None:
        """Reject prompts that would be truncated by the static T5 graph."""

        sequences = list(texts) if not isinstance(texts, str) else [texts]
        if not all(isinstance(text, str) for text in sequences):
            raise TypeError("T5 prompts must be strings")
        if self.tokenizer.clean:
            sequences = [self.tokenizer._clean(text) for text in sequences]
        tokenized = self.tokenizer.tokenizer(
            sequences,
            add_special_tokens=True,
            padding=False,
            truncation=False,
        )
        lengths = [len(ids) for ids in tokenized["input_ids"]]
        too_long = [(index, length) for index, length in enumerate(lengths) if length > self.text_len]
        if too_long:
            details = ", ".join(f"prompt[{index}]={length}" for index, length in too_long)
            raise ValueError(
                f"T5 {prompt_name} exceeds the model limit of {self.text_len} tokens: "
                f"{details}. Shorten the prompt instead of relying on truncation."
            )

    def __call__(self, texts: Sequence[str], prompt_name: str = "prompt") -> list[torch.Tensor]:
        with self.perf.scope(f"{PERF_ROOT}.t5"):
            with self.perf.scope(f"{PERF_ROOT}.t5.preprocess"):
                # Check before the tokenizer's static-length truncation can occur.
                self._validate_text_lengths(texts, prompt_name)
                ids, mask = self.tokenizer(texts, return_mask=True, add_special_tokens=True)
                ids, mask = ids.to(self.device), mask.to(self.device)
                lengths = mask.gt(0).sum(dim=1).long().cpu().tolist()
                embeddings = self.embedding(ids.long()).to(dtype=self.dtype)
                mask4d = mask.view(mask.shape[0], 1, 1, -1)
                bias = torch.zeros(mask4d.shape, device=self.device, dtype=self.dtype).masked_fill(
                    mask4d == 0, -65504.0
                )
            context = self.runtime({"inputs_embeds": embeddings, "mask_bias": bias})
            return [item[:length] for item, length in zip(context, lengths, strict=True)]


class DiTTimeFrontend(nn.Module):
    """Recreate the graph-external timestep embedding/projection layers."""

    REQUIRED_KEYS = (
        "time_embedding.0.bias",
        "time_embedding.0.weight",
        "time_embedding.2.bias",
        "time_embedding.2.weight",
        "time_projection.1.bias",
        "time_projection.1.weight",
    )

    def __init__(
        self,
        frontend_file: Path,
        runtime: TcimRuntimeModel,
        device: torch.device,
    ):
        super().__init__()
        saved_state = _load_pt_state(frontend_file)
        missing = [key for key in self.REQUIRED_KEYS if key not in saved_state]
        if missing:
            raise KeyError(f"missing timestep frontend weights in {frontend_file}: {missing}")
        state = {key: saved_state[key].float() for key in self.REQUIRED_KEYS}
        first_weight = state["time_embedding.0.weight"]
        second_weight = state["time_embedding.2.weight"]
        projection_weight = state["time_projection.1.weight"]
        self.dim = int(first_weight.shape[0])
        self.freq_dim = int(first_weight.shape[1])
        if tuple(second_weight.shape) != (self.dim, self.dim):
            raise ValueError(f"unexpected time_embedding.2 shape: {second_weight.shape}")
        if tuple(projection_weight.shape) != (self.dim * 6, self.dim):
            raise ValueError(f"unexpected time_projection.1 shape: {projection_weight.shape}")
        e_shape = runtime.input_shapes.get("e")
        e0_shape = runtime.input_shapes.get("e0")
        if e_shape is None or e0_shape is None:
            raise KeyError(f"{runtime.name} must expose e/e0 inputs")
        if e_shape[-1] != self.dim or tuple(e0_shape[-2:]) != (6, self.dim):
            raise ValueError(
                f"{runtime.name} timestep inputs do not match frontend: " f"e={e_shape}, e0={e0_shape}, dim={self.dim}"
            )
        self.time_embedding = nn.Sequential(
            nn.Linear(self.freq_dim, self.dim),
            nn.SiLU(),
            nn.Linear(self.dim, self.dim),
        )
        self.time_projection = nn.Sequential(nn.SiLU(), nn.Linear(self.dim, self.dim * 6))
        self.load_state_dict(state, strict=True)
        self.eval().requires_grad_(False).to(device=device, dtype=torch.float32)
        self.device = device

    def forward(self, timestep: torch.Tensor, seq_len: int) -> tuple[torch.Tensor, torch.Tensor]:
        # The compiled DiT expects one embedding per sequence position.
        timestep = timestep.to(self.device)
        if timestep.dim() == 1:
            timestep = timestep.expand(timestep.size(0), seq_len)
        batch = timestep.size(0)
        sinusoid = sinusoidal_embedding_1d(self.freq_dim, timestep.flatten()).unflatten(0, (batch, seq_len)).float()
        e = self.time_embedding(sinusoid)
        e0 = self.time_projection(e).unflatten(2, (6, self.dim))
        return e.half(), e0.half()


class HmmDiT:
    """Prepare static DiT inputs and execute one HMM forward pass."""

    def __init__(
        self,
        runtime: TcimRuntimeModel,
        frontend_file: Path,
        device: torch.device,
    ):
        self.runtime = runtime
        self.device = device
        self.perf = runtime.perf
        expected = {"latent", "context", "e", "e0"}
        if set(runtime.input_shapes) != expected:
            raise ValueError(f"{runtime.name} expects HMM inputs {sorted(expected)}, " f"got {runtime.input_shapes}")
        self.seq_len = int(runtime.input_shapes["e"][1])
        if runtime.input_shapes["e0"][1] != self.seq_len:
            raise ValueError(f"{runtime.name} e/e0 sequence mismatch")
        self.time_frontend = DiTTimeFrontend(frontend_file, runtime, device)
        self._warned_context_lengths: set[int] = set()

    def validate_latent_condition(self, latent: torch.Tensor, y: torch.Tensor | None):
        expected = self.runtime.input_shapes["latent"]
        actual = tuple(latent.shape)
        if y is not None:
            actual = (latent.shape[0] + y.shape[0], *latent.shape[1:])
        if actual != expected:
            raise ValueError(
                f"{self.runtime.name}.latent shape mismatch after conditioning: " f"HMM={expected}, input={actual}"
            )

    def _context(self, context: torch.Tensor) -> torch.Tensor:
        expected = self.runtime.input_shapes["context"]
        if len(expected) == 3:
            target_len = expected[1]
            context = context.unsqueeze(0) if context.dim() == 2 else context
            actual_len = context.shape[1]
            context = context[:, :target_len]
            if context.shape[1] < target_len:
                context = F.pad(context, (0, 0, 0, target_len - context.shape[1]))
        elif len(expected) == 2:
            target_len = expected[0]
            context = context[0] if context.dim() == 3 else context
            actual_len = context.shape[0]
            context = context[:target_len]
            if context.shape[0] < target_len:
                context = F.pad(context, (0, 0, 0, target_len - context.shape[0]))
        else:
            raise ValueError(f"unsupported DiT context shape: {expected}")
        if actual_len > target_len and actual_len not in self._warned_context_lengths:
            logger.warning(
                f"{self.runtime.name} context length is static ({target_len}); "
                f"input length {actual_len} will be truncated."
            )
            self._warned_context_lengths.add(actual_len)
        return context.to(self.device, dtype=torch.float16)

    def __call__(self, latent, context, timestep, y=None):
        # I2V concatenates the 16-channel noisy latent with the 20-channel
        # VAE/mask condition before binding the combined tensor to the graph.
        with self.perf.scope(f"{PERF_ROOT}.{self.runtime.name}.preprocess"):
            self.validate_latent_condition(latent, y)
            runtime_latent = latent.to(self.device, dtype=torch.float16)
            if y is not None:
                runtime_latent = torch.cat([runtime_latent, y.to(self.device, dtype=torch.float16)], dim=0)
            context_input = self._context(context)
            e, e0 = self.time_frontend(timestep, self.seq_len)
            inputs = {
                "latent": runtime_latent,
                "context": context_input,
                "e": e,
                "e0": e0,
            }
        return self.runtime(inputs)


class HmmVAE:
    def __init__(
        self,
        runtime: TcimRuntimeModel,
        input_name: str,
        device: torch.device,
        clamp=False,
    ):
        self.runtime = runtime
        self.input_name = input_name
        self.device = device
        self.perf = runtime.perf
        self.clamp = clamp
        if set(runtime.input_shapes) != {input_name}:
            raise ValueError(f"{runtime.name} must expose only {input_name!r}, " f"got {runtime.input_shapes}")

    def __call__(self, tensor):
        # VAE execution is on the configured HOUMO device; only the returned
        # frame/latent tensor is materialized as a host PyTorch tensor.
        with self.perf.scope(f"{PERF_ROOT}.{self.runtime.name}"):
            with self.perf.scope(f"{PERF_ROOT}.{self.runtime.name}.preprocess"):
                expected_shape = self.runtime.input_shapes[self.input_name]
                if tuple(tensor.shape) != expected_shape:
                    raise ValueError(
                        f"{self.runtime.name}.{self.input_name} shape mismatch: "
                        f"HMM={expected_shape}, input={tuple(tensor.shape)}"
                    )
                tensor = tensor.to(self.device, dtype=torch.float16)
                tensor = tensor.contiguous()
            output = self.runtime({self.input_name: tensor})
            with self.perf.scope(f"{PERF_ROOT}.{self.runtime.name}.postprocess"):
                output = output.to(self.device)
                output = output.float().clamp_(-1, 1) if self.clamp else output.half()
            return output


class Wan22HmmPipeline:
    """Wan2.2 preprocessing, dual-DiT sampling and VAE postprocessing.

    All Python-side work uses CPU tensors. Each HMM component is loaded once
    and remains resident on its assigned HOUMO device until ``release()``.
    """

    def __init__(
        self,
        args,
        model_paths: dict[str, Path],
        device_managers: dict[int, object],
        frontend_files: dict[str, Path],
        tokenizer_path: Path,
        cfg,
    ):
        self.args = args
        self.cfg = cfg
        self.perf = PerfTracker.create(True)
        # All graph-external work is intentionally CPU-only.  HMM execution is
        # handled independently by tcim_lite on the configured HOUMO devices.
        self.device = torch.device("cpu")
        component_devices = {
            "t5": args.t5_device,
            "vae_decode": args.vae_decode_device,
            "low_noise_model": args.low_noise_device,
            "high_noise_model": args.high_noise_device,
        }
        if args.task.startswith("i2v"):
            component_devices["vae_encode"] = args.vae_encode_device
        logger.info("[HMM] Component device mapping:", flush=True)
        for name, device_id in component_devices.items():
            logger.info(f"  {name}: device {device_id}", flush=True)
        self.runtimes = {
            name: TcimRuntimeModel(
                name,
                model_path,
                component_devices[name],
                device_managers[component_devices[name]],
                self.perf,
            )
            for name, model_path in model_paths.items()
        }

        self.t5 = HmmT5(
            self.runtimes["t5"],
            frontend_files["t5"],
            tokenizer_path,
            self.device,
        )
        self.vae_encoder = (
            HmmVAE(self.runtimes["vae_encode"], "video", self.device) if args.task.startswith("i2v") else None
        )
        self.vae_decoder = HmmVAE(self.runtimes["vae_decode"], "latent", self.device, clamp=True)
        self.low_noise = HmmDiT(
            self.runtimes["low_noise_model"],
            frontend_files["low_noise_model"],
            self.device,
        )
        self.high_noise = HmmDiT(
            self.runtimes["high_noise_model"],
            frontend_files["high_noise_model"],
            self.device,
        )
        self._validate_model_set()
        if args.boundary is not None and not 0.0 <= args.boundary <= 1.0:
            raise ValueError(f"--boundary must be in [0, 1], got {args.boundary}")
        train_steps = int(cfg.num_train_timesteps)
        self.boundary_override = None if args.boundary is None else float(args.boundary) * train_steps
        self.config_boundary = float(cfg.boundary) * train_steps

    def _validate_model_set(self):
        low_shapes = self.low_noise.runtime.input_shapes
        high_shapes = self.high_noise.runtime.input_shapes
        if low_shapes != high_shapes:
            raise ValueError(f"high/low DiT HMM signatures differ: low={low_shapes}, high={high_shapes}")
        dit_latent = low_shapes["latent"]
        vae_latent = self.vae_decoder.runtime.input_shapes["latent"]
        if tuple(dit_latent[1:]) != tuple(vae_latent[1:]):
            raise ValueError(f"DiT/VAE latent dimensions differ: DiT={dit_latent}, VAE={vae_latent}")
        if self.args.task.startswith("i2v"):
            if dit_latent[0] <= vae_latent[0]:
                raise ValueError(f"i2v DiT must contain condition channels: {dit_latent} vs {vae_latent}")
        elif dit_latent != vae_latent:
            raise ValueError(f"t2v DiT latent must match VAE latent: {dit_latent} vs {vae_latent}")

    def resolve_video_shape(self) -> tuple[tuple[int, int], int]:
        if self.args.task.startswith("i2v"):
            _, frame_num, height, width = self.vae_encoder.runtime.input_shapes["video"]
        else:
            _, latent_frames, latent_height, latent_width = self.vae_decoder.runtime.input_shapes["latent"]
            stride = tuple(int(value) for value in self.cfg.vae_stride)
            frame_num = (latent_frames - 1) * stride[0] + 1
            height = latent_height * stride[1]
            width = latent_width * stride[2]
        size = (int(width), int(height))
        frame_num = int(frame_num)
        if self.args.size is not None and tuple(self.args.size) != size:
            raise ValueError(f"--size={tuple(self.args.size)} does not match HMM size={size}")
        if self.args.frame_num is not None and self.args.frame_num != frame_num:
            raise ValueError(f"--frame-num={self.args.frame_num} does not match HMM " f"frame count={frame_num}")
        return size, frame_num

    def _scheduler(self, steps, shift, solver):
        # Scheduler state and timestep tensors are host-side; only the model
        # evaluations for each timestep execute on HMM devices.
        if solver == "unipc":
            scheduler = FlowUniPCMultistepScheduler(
                num_train_timesteps=self.cfg.num_train_timesteps,
                shift=1,
                use_dynamic_shifting=False,
            )
            scheduler.set_timesteps(steps, device=self.device, shift=shift)
            return scheduler, scheduler.timesteps, None
        if solver == "dpm++":
            scheduler = FlowDPMSolverMultistepScheduler(
                num_train_timesteps=self.cfg.num_train_timesteps,
                shift=1,
                use_dynamic_shifting=False,
            )
            timesteps = retrieve_timesteps(
                scheduler,
                device=self.device,
                sigmas=get_sampling_sigmas(steps, shift),
            )[0]
            return scheduler, timesteps, None
        if solver == "euler":
            sigmas = torch.linspace(1.0, 0.0, steps + 1, device=self.device, dtype=torch.float32)
            sigmas = shift * sigmas / (1 + (shift - 1) * sigmas)
            timesteps = (sigmas[:-1] * int(self.cfg.num_train_timesteps)).to(dtype=torch.int64)
            return None, timesteps, sigmas
        raise NotImplementedError(f"unsupported sample solver: {solver}")

    def _sampling_boundary(self, timesteps, guide_scale):
        if self.boundary_override is not None:
            return self.boundary_override
        if tuple(guide_scale) == (1.0, 1.0):
            middle = len(timesteps) // 2
            if middle == 0:
                raise ValueError("dynamic boundary requires at least two steps")
            return ((timesteps[middle - 1] + timesteps[middle]) * 0.5).item()
        return self.config_boundary

    def _sample(
        self,
        latent,
        y,
        context,
        context_null,
        steps,
        shift,
        solver,
        guide_scale,
        generator,
    ):
        # Every sampling step performs conditional and unconditional forwards;
        # CFG combines them before the scheduler advances the latent.
        scheduler, timesteps, sigmas = self._scheduler(steps, shift, solver)
        boundary = self._sampling_boundary(timesteps, guide_scale)
        logger.info(
            f"Sampling solver={solver}, "
            f"timesteps={[int(item) for item in timesteps.tolist()]}, "
            f"expert_boundary={boundary:.3f}",
            flush=True,
        )
        active_expert = None
        for step_index, timestep in enumerate(tqdm(timesteps, desc="Wan2.2 HMM sampling")):
            # Noise experts are selected by the timestep boundary. They are
            # loaded on separate devices, so switching does not reload either.
            expert = self.high_noise if timestep.item() >= boundary else self.low_noise
            if active_expert is not None and expert is not active_expert:
                tqdm.write(
                    f"[DiT] Switching expert: {active_expert.runtime.name} -> "
                    f"{expert.runtime.name}; both HMMs remain resident"
                )
            elif active_expert is None:
                tqdm.write(f"[DiT] Activating expert: {expert.runtime.name}")
            active_expert = expert
            scale = guide_scale[1] if timestep.item() >= boundary else guide_scale[0]
            tqdm.write(
                f"[DiT] Step {step_index + 1}/{len(timesteps)}: "
                f"timestep={timestep.item():.3f}, "
                f"expert={expert.runtime.name}, guide_scale={scale:.6f}"
            )
            with self.perf.scope(f"{PERF_ROOT}.{expert.runtime.name}"):
                t = timestep.reshape(1).to(self.device)
                pred_cond = expert(latent, context[0], t, y).to(self.device)
                pred_null = expert(latent, context_null[0], t, y).to(self.device)
                with self.perf.scope(f"{PERF_ROOT}.{expert.runtime.name}.postprocess"):
                    prediction = pred_null + scale * (pred_cond - pred_null)
                    if solver == "euler":
                        sigma = sigmas[step_index]
                        sigma_next = sigmas[step_index + 1]
                        denoised = latent - sigma * prediction
                        derivative = (latent - denoised) / sigma
                        latent = latent + derivative * (sigma_next - sigma)
                    else:
                        latent = scheduler.step(
                            prediction.unsqueeze(0),
                            timestep,
                            latent.unsqueeze(0),
                            return_dict=False,
                            generator=generator,
                        )[0].squeeze(0)
        return latent

    @torch.no_grad()
    def generate_i2v(
        self,
        prompt,
        negative_prompt,
        image,
        size,
        frame_num,
        steps,
        shift,
        solver,
        guide_scale,
        seed,
    ):
        # The image is letterboxed to the static VAE input size; the remaining
        # frames are zero placeholders and are completed by diffusion sampling.
        width, height = size
        image = _resize_with_letterbox(image, width, height)
        image = torch.from_numpy(np.asarray(image, dtype=np.float32).copy()).permute(2, 0, 1) / 127.5 - 1
        expected_latent = self.vae_decoder.runtime.input_shapes["latent"]
        latent_channels, latent_frames, lat_h, lat_w = expected_latent
        patch = self.cfg.patch_size
        seq_len = latent_frames * lat_h * lat_w // (patch[1] * patch[2])
        if seq_len != self.low_noise.seq_len:
            raise ValueError(f"DiT sequence mismatch: HMM={self.low_noise.seq_len}, " f"derived={seq_len}")
        generator = torch.Generator(device=self.device).manual_seed(seed)
        latent = torch.randn(
            expected_latent,
            generator=generator,
            device=self.device,
            dtype=torch.float32,
        )
        mask = torch.ones(1, frame_num, lat_h, lat_w, device=self.device)
        mask[:, 1:] = 0
        mask = torch.cat([mask[:, :1].repeat_interleave(4, dim=1), mask[:, 1:]], dim=1)
        mask = mask.view(1, mask.shape[1] // 4, 4, lat_h, lat_w).transpose(1, 2)[0]
        video = torch.cat(
            [
                F.interpolate(
                    image[None],
                    size=(height, width),
                    mode="bicubic",
                    align_corners=False,
                ).transpose(0, 1),
                torch.zeros(3, frame_num - 1, height, width),
            ],
            dim=1,
        ).to(self.device)
        encoded = self.vae_encoder(video)
        y = torch.cat([mask, encoded.to(self.device)], dim=0)
        context = [item.to(self.device) for item in self.t5([prompt], "positive prompt")]
        context_null = [item.to(self.device) for item in self.t5([negative_prompt], "negative prompt")]

        latent = self._sample(latent, y, context, context_null, steps, shift, solver, guide_scale, generator)
        video = self.vae_decoder(latent)
        return video

    @torch.no_grad()
    def generate_t2v(
        self,
        prompt,
        negative_prompt,
        size,
        frame_num,
        steps,
        shift,
        solver,
        guide_scale,
        seed,
    ):
        # T2V starts from CPU-generated Gaussian noise and has no VAE condition.
        width, height = size
        stride, patch = self.cfg.vae_stride, self.cfg.patch_size
        expected_latent = self.vae_decoder.runtime.input_shapes["latent"]
        latent_shape = (
            expected_latent[0],
            (frame_num - 1) // stride[0] + 1,
            height // stride[1],
            width // stride[2],
        )
        if latent_shape != expected_latent:
            raise ValueError(f"VAE latent mismatch: HMM={expected_latent}, derived={latent_shape}")
        seq_len = math.ceil(latent_shape[2] * latent_shape[3] / (patch[1] * patch[2]) * latent_shape[1])
        if seq_len != self.low_noise.seq_len:
            raise ValueError(f"DiT sequence mismatch: HMM={self.low_noise.seq_len}, " f"derived={seq_len}")
        generator = torch.Generator(device=self.device).manual_seed(seed)
        latent = torch.randn(
            latent_shape,
            generator=generator,
            device=self.device,
            dtype=torch.float32,
        )
        context = [item.to(self.device) for item in self.t5([prompt], "positive prompt")]
        context_null = [item.to(self.device) for item in self.t5([negative_prompt], "negative prompt")]

        latent = self._sample(latent, None, context, context_null, steps, shift, solver, guide_scale, generator)
        video = self.vae_decoder(latent)
        return video

    def release(self):
        for runtime in self.runtimes.values():
            runtime.release()


def _sampling_args(args, cfg):
    steps = int(args.sample_steps)
    if steps <= 0:
        raise ValueError(f"--sample-steps must be positive, got {steps}")
    shift = float(args.sample_shift)
    if len(args.guide_scale) == 1:
        guide_scale = (float(args.guide_scale[0]),) * 2
    elif len(args.guide_scale) == 2:
        guide_scale = tuple(float(value) for value in args.guide_scale)
    else:
        raise ValueError("--guide-scale expects one or two numbers")
    return steps, shift, guide_scale


def _save(video: torch.Tensor, path: Path, fps: int):
    # Convert the decoded [-1, 1] RGB tensor to an H.264 MP4 through imageio.
    from wan.utils.utils import save_video as wan_save_video

    video = video.detach().cpu()
    if video.ndim == 5 and video.shape[0] == 1:
        video = video.squeeze(0)
    if video.ndim != 4:
        raise ValueError(f"expected decoded video [C,T,H,W], got {tuple(video.shape)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    wan_save_video(video.unsqueeze(0), save_file=str(path), fps=fps, nrow=1)
    logger.info(f"Saved video: {path.resolve()} shape={tuple(video.shape)}", flush=True)


def _build_model_paths(args) -> dict[str, Path]:
    # I2V adds the VAE encoder; T2V needs only the decoder and DiT experts.
    paths = {
        "t5": args.t5_hmm,
        "vae_decode": args.vae_decode_hmm,
        "low_noise_model": args.low_noise_hmm,
        "high_noise_model": args.high_noise_hmm,
    }
    if args.task.startswith("i2v"):
        paths["vae_encode"] = args.vae_encode_hmm
    return {name: _required_path(path, f"{name} HMM") for name, path in paths.items()}


def main(args):
    # Resolve model/frontend paths and read static HMM signatures before
    # allocating runtime state, so shape errors fail early.
    model_paths = _build_model_paths(args)
    frontend_files = {
        "t5": _required_path(args.t5_frontend, "T5 frontend weights"),
        "low_noise_model": _required_path(args.low_noise_frontend, "low-noise timestep frontend weights"),
        "high_noise_model": _required_path(args.high_noise_frontend, "high-noise timestep frontend weights"),
    }
    tokenizer_path = _required_path(args.tokenizer_path, "T5 tokenizer", directory=True)
    cfg = WAN_CONFIGS[args.task]
    component_device_ids = {
        args.t5_device,
        args.vae_decode_device,
        args.low_noise_device,
        args.high_noise_device,
    }
    if args.task.startswith("i2v"):
        component_device_ids.add(args.vae_encode_device)

    # A DevManager is shared by components assigned to the same HOUMO device.
    device_managers = {}
    for device_id in sorted(component_device_ids):
        if device_id < 0:
            raise ValueError(f"HOUMO device id must be non-negative, got {device_id}")
        device_managers[device_id] = tcim.runtime.DevManager([device_id], "Xh2HalBackend")
    pipeline = Wan22HmmPipeline(
        args,
        model_paths,
        device_managers,
        frontend_files,
        tokenizer_path,
        cfg,
    )
    size, frame_num = pipeline.resolve_video_shape()
    logger.info(
        f"[HMM] task={args.task} size={size} frame_num={frame_num} " "preprocess_device=cpu",
        flush=True,
    )
    try:
        with pipeline.perf.scope(PERF_ROOT):
            negative_prompt = args.negative_prompt or cfg.sample_neg_prompt
            prompt = args.prompt or (DEFAULT_PROMPT_I2V if args.task.startswith("i2v") else DEFAULT_PROMPT_T2V)
            steps, shift, guide_scale = _sampling_args(args, cfg)
            if args.task.startswith("i2v"):
                image_path = _required_path(args.image, "i2v input image")
                video = pipeline.generate_i2v(
                    prompt,
                    negative_prompt,
                    Image.open(image_path),
                    size,
                    frame_num,
                    steps,
                    shift,
                    args.sample_solver,
                    guide_scale,
                    args.seed,
                )
            else:
                video = pipeline.generate_t2v(
                    prompt,
                    negative_prompt,
                    size,
                    frame_num,
                    steps,
                    shift,
                    args.sample_solver,
                    guide_scale,
                    args.seed,
                )
            with pipeline.perf.scope(f"{PERF_ROOT}.video_save"):
                _save(video, Path(args.output), args.fps)
    finally:
        pipeline.release()
        pipeline.perf.print_summary()
        gc.collect()


if __name__ == "__main__":
    main(parse_args())
