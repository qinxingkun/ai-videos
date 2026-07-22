# ComfyUI + Wan 2.2 视频生成模型部署文档

> 本文档详细说明如何使用 ComfyUI 部署阿里云通义万相 Wan 2.2 视频生成模型，涵盖环境搭建、模型下载、工作流配置及故障排查。

---

## 目录

1. [概述](#1-概述)
2. [系统要求](#2-系统要求)
3. [ComfyUI 安装](#3-comfyui-安装)
4. [Wan 2.2 模型下载与放置](#4-wan-22-模型下载与放置)
5. [工作流配置与使用](#5-工作流配置与使用)
6. [低显存方案](#6-低显存方案)
7. [常见问题排查](#7-常见问题排查)
8. [附录](#8-附录)

---

## 1. 概述

### 1.1 Wan 2.2 简介

Wan 2.2 是阿里云通义万相推出的新一代多模态视频生成模型，采用 **MoE（Mixture of Experts）混合专家架构**，由高噪声和低噪声专家模型协同工作，根据去噪时间步动态分配专家，从而生成更高质量的视频内容。

核心特性：
- **电影级美学控制** — 深度融合专业影视美学标准，支持光线、色彩、构图等多维视觉控制
- **大规模复杂运动** — 流畅还原各种复杂运动，提升运动可控性和自然度
- **精准语义遵循** — 擅长复杂场景和多对象生成，更好还原用户创作意图

### 1.2 开源模型版本

Wan 2.2 系列基于 **Apache 2.0 开源协议**，支持商业使用。

| 模型类型 | 模型名称 | 参数量 | 主要功能 |
|----------|----------|--------|----------|
| **混合模型** | Wan2.2-TI2V-5B | 5B | 同时支持文生视频和图生视频 |
| **文生视频** | Wan2.2-T2V-A14B | 14B | 从文本描述生成高质量视频 |
| **图生视频** | Wan2.2-I2V-A14B | 14B | 将静态图像转换为动态视频 |

### 1.3 ComfyUI 简介

ComfyUI 是一个基于节点式工作流的 AI 图像/视频生成框架，具有以下优势：
- **智能内存管理** — 可在仅 1GB VRAM 的 GPU 上自动运行大模型（通过 offloading 机制）
- **异步队列系统** — 只重新执行工作流中发生变化的部分
- **完全离线运行** — 核心程序不会下载任何东西，除非用户主动操作

> **仓库地址**：https://github.com/Comfy-Org/ComfyUI

---

## 2. 系统要求

### 2.1 硬件要求

#### GPU 显存需求

| 模型版本 | 最低 VRAM | 推荐 VRAM | 说明 |
|----------|-----------|-----------|------|
| **5B 混合版** | 8 GB | 12 GB+ | 借助 ComfyUI offloading 机制可在 8GB 显存运行 |
| **14B T2V/I2V** | 16 GB | 24 GB+ | 需同时加载高噪声和低噪声两个专家模型 |
| **14B FLF2V** | 16 GB | 24 GB+ | 复用 I2V 模型文件 |

#### 支持的 GPU 类型

| GPU 类型 | 支持情况 | 备注 |
|----------|----------|------|
| NVIDIA | ✅ 完全支持 | 20 系列及以上推荐；10 系列需使用 cu126 版本 |
| AMD | ⚠️ 实验性 | Linux: ROCm 7.2；Windows: RDNA 3/3.5/4 实验性支持 |
| Intel Arc | ⚠️ 实验性 | 通过 torch.xpu 支持 |
| Apple Silicon | ✅ 支持 | M1-M4 |
| CPU only | ⚠️ 极慢 | 使用 `--cpu` 参数，仅用于测试 |

### 2.2 软件要求

| 软件 | 版本要求 | 说明 |
|------|----------|------|
| **Python** | 3.13（推荐）/ 3.12（回退） | 3.14 可用但部分自定义节点可能有问题 |
| **PyTorch** | ≥ 2.5 | 推荐最新主要版本 + 最新 CUDA 版本；已放弃 2.4 支持 |
| **Git** | 最新版 | 用于克隆仓库 |
| **CUDA** | 12.6 / 13.0 | 根据 GPU 型号选择 |

---

## 3. ComfyUI 安装

### 3.1 方式一：手动安装（推荐开发者）

#### 步骤 1：克隆仓库

```bash
git clone https://github.com/Comfy-Org/ComfyUI.git
cd ComfyUI
```

#### 步骤 2：创建虚拟环境

```bash
python -m venv venv

# Windows 激活：
venv\Scripts\activate

# Linux/macOS 激活：
source venv/bin/activate
```

#### 步骤 3：安装 PyTorch

根据 GPU 类型选择对应的安装命令：

**NVIDIA GPU（CUDA 13.0 — 推荐）：**
```bash
pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu130
```

**NVIDIA GPU（CUDA 13.2 Nightly — 可能有性能提升）：**
```bash
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu132
```

**NVIDIA 10 系列及更早（CUDA 12.6）：**
```bash
pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu126
```

**AMD GPU（Linux, ROCm 7.2）：**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm7.2
```

**Intel GPU：**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/xpu
```

#### 步骤 4：安装 ComfyUI 依赖

```bash
pip install -r requirements.txt
```

#### 步骤 5：启动 ComfyUI

```bash
python main.py
```

启动成功后，浏览器访问 **http://127.0.0.1:8188** 即可进入 ComfyUI 界面。

### 3.2 方式二：Windows 便携版（推荐新手）

直接从 GitHub Releases 页面下载对应 GPU 的便携版压缩包：

| 版本 | 下载地址 | 适用场景 |
|------|----------|----------|
| NVIDIA GPU 版 | [ComfyUI_windows_portable_nvidia.7z](https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z) | Python 3.13 + PyTorch CUDA 13.0 |
| NVIDIA cu126 版 | [ComfyUI_windows_portable_nvidia_cu126.7z](https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia_cu126.7z) | Python 3.12 + CUDA 12.6，支持 GTX 10 系列 |
| AMD GPU 版 | [ComfyUI_windows_portable_amd.7z](https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_amd.7z) | AMD 显卡 |
| Intel GPU 版 | [ComfyUI_windows_portable_intel.7z](https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_intel.7z) | Intel Arc 显卡 |

解压后，双击 `run_nvidia_gpu.bat`（或其他对应脚本）即可启动。

### 3.3 方式三：桌面应用

最简单的安装方式，支持 Windows 和 macOS：
- 下载地址：https://www.comfy.org/download

### 3.4 方式四：comfy-cli 安装

```bash
pip install comfy-cli
comfy install
```

### 3.5 常用启动参数

| 参数 | 说明 |
|------|------|
| `--cpu` | 无 GPU 时使用 CPU 运行（极慢，仅测试用） |
| `--preview-method auto` | 启用预览 |
| `--preview-method taesd` | 高质量预览（需下载 TAESD 解码器） |
| `--listen 0.0.0.0` | 允许局域网访问 |
| `--port 8188` | 指定端口（默认 8188） |

---

## 4. Wan 2.2 模型下载与放置

### 4.1 模型来源

模型可从以下两个平台下载：

| 平台 | 仓库地址 | 说明 |
|------|----------|------|
| **ModelScope（国内推荐）** | https://www.modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged | 国内访问速度快 |
| **HuggingFace** | https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged | 官方原始仓库 |

### 4.2 必需的公共文件

所有 Wan 2.2 模型变体都需要以下公共组件：

#### Text Encoder（文本编码器）

| 文件名 | 放置路径 | 说明 |
|--------|----------|------|
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `ComfyUI/models/text_encoders/` | 所有 Wan 2.2 模型共用 |

#### VAE（变分自编码器）

| 文件名 | 放置路径 | 适用模型 | 说明 |
|--------|----------|----------|------|
| `wan2.2_vae.safetensors` | `ComfyUI/models/vae/` | **仅 5B 混合版** | Wan 2.2 专用 VAE |
| `wan_2.1_vae.safetensors` | `ComfyUI/models/vae/` | **14B 版本** | Wan 2.1 VAE（14B 模型仍使用此 VAE） |

> ⚠️ **注意**：5B 和 14B 版本使用**不同的 VAE 文件**，切勿混淆！

### 4.3 Diffusion 模型文件（按模型版本选择）

#### 5B 混合版（TI2V）

仅需一个模型文件：

| 文件名 | 放置路径 | 精度 |
|--------|----------|------|
| `wan2.2_ti2v_5B_fp16.safetensors` | `ComfyUI/models/diffusion_models/` | fp16 |

#### 14B 文生视频（T2V）

需要两个专家模型（高噪声 + 低噪声）：

| 文件名 | 放置路径 | 精度 |
|--------|----------|------|
| `wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors` | `ComfyUI/models/diffusion_models/` | fp8 scaled |
| `wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors` | `ComfyUI/models/diffusion_models/` | fp8 scaled |

#### 14B 图生视频（I2V）

需要两个专家模型：

| 文件名 | 放置路径 | 精度 |
|--------|----------|------|
| `wan2.2_i2v_high_noise_14B_fp16.safetensors` | `ComfyUI/models/diffusion_models/` | fp16 |
| `wan2.2_i2v_low_noise_14B_fp16.safetensors` | `ComfyUI/models/diffusion_models/` | fp16 |

### 4.4 完整目录结构

#### 5B 混合版部署结构

```
ComfyUI/
├── 📂 models/
│   ├── 📂 diffusion_models/
│   │   └── wan2.2_ti2v_5B_fp16.safetensors
│   ├── 📂 text_encoders/
│   │   └── umt5_xxl_fp8_e4m3fn_scaled.safetensors
│   └── 📂 vae/
│       └── wan2.2_vae.safetensors
```

#### 14B T2V 部署结构

```
ComfyUI/
├── 📂 models/
│   ├── 📂 diffusion_models/
│   │   ├── wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors
│   │   └── wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors
│   ├── 📂 text_encoders/
│   │   └── umt5_xxl_fp8_e4m3fn_scaled.safetensors
│   └── 📂 vae/
│       └── wan_2.1_vae.safetensors
```

#### 14B I2V 部署结构

```
ComfyUI/
├── 📂 models/
│   ├── 📂 diffusion_models/
│   │   ├── wan2.2_i2v_high_noise_14B_fp16.safetensors
│   │   └── wan2.2_i2v_low_noise_14B_fp16.safetensors
│   ├── 📂 text_encoders/
│   │   └── umt5_xxl_fp8_e4m3fn_scaled.safetensors
│   └── 📂 vae/
│       └── wan_2.1_vae.safetensors
```

### 4.5 从 ModelScope 下载模型

#### 方法一：使用 modelscope CLI（推荐）

```bash
# 安装 modelscope CLI
pip install modelscope

# 下载单个文件到指定目录
modelscope download --model Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  --include "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
  --local_dir ./download_tmp

# 然后手动将文件拷贝到 ComfyUI 对应目录
```

#### 方法二：使用 Git LFS 克隆整个仓库

```bash
# 安装 Git LFS
git lfs install

# 克隆仓库（注意：整个仓库约 470GB，不推荐全量下载）
git clone https://www.modelscope.cn/Comfy-Org/Wan_2.2_ComfyUI_Repackaged.git
```

> ⚠️ **强烈建议**：仅下载所需的模型文件，避免全量克隆（整个仓库约 470GB）。

#### 方法三：浏览器手动下载

访问 https://www.modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/files ，逐个点击所需文件进行下载，然后手动放置到 ComfyUI 对应目录。

#### 方法四：使用 huggingface-cli（适用于 HuggingFace）

```bash
# 安装 huggingface_hub
pip install huggingface_hub

# 下载单个文件
huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors \
  --local-dir ./download_tmp

# 下载整个子目录（如所有 diffusion_models）
huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  --include "split_files/diffusion_models/*" \
  --local-dir ./download_tmp
```

下载完成后，将文件从 `download_tmp/split_files/` 拷贝到 ComfyUI 对应目录：

```bash
# 示例：拷贝 5B 版本所需的全部模型
cp download_tmp/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors \
   ComfyUI/models/diffusion_models/

cp download_tmp/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
   ComfyUI/models/text_encoders/

cp download_tmp/split_files/vae/wan2.2_vae.safetensors \
   ComfyUI/models/vae/
```

---

## 5. 工作流配置与使用

### 5.1 通用前提

1. 确保 ComfyUI 已更新至**最新版本**（推荐 Nightly 版本）
2. 所有模型文件已放置到正确目录
3. 启动 ComfyUI 并浏览器访问 http://127.0.0.1:8188

### 5.2 加载工作流模板

通过菜单 **Workflow → Browse Templates → Video** 查找 Wan 2.2 对应的工作流模板。

如果找不到模板，说明 ComfyUI 版本过旧，请先更新。

### 5.3 工作流一：5B 混合版 — 文生视频（T2V）

#### 模型节点配置

| 节点 | 加载文件 |
|------|----------|
| `Load Diffusion Model` | `wan2.2_ti2v_5B_fp16.safetensors` |
| `Load CLIP` | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` |
| `Load VAE` | `wan2.2_vae.safetensors` |

#### 操作步骤

1. 加载工作流模板或导入 JSON 文件
2. 在 `CLIP Text Encode`（正向提示词）节点中输入视频描述
3. 在 `CLIP Text Encode`（反向提示词）节点中输入排除内容
4. 可在 `EmptyHunyuanLatentVideo` 节点中调整视频尺寸和帧数
5. 点击 **Run** 按钮（快捷键 `Ctrl+Enter`）执行生成

#### 示例提示词

**正向提示词：**
```
A beautiful sunset over a calm ocean, golden light reflecting on the water, cinematic, high quality
```

**反向提示词：**
```
low quality, blurry, distorted, artifacts
```

#### 工作流 JSON 下载

- [text_to_video_wan22_5B.json](https://comfyanonymous.github.io/ComfyUI_examples/wan22/text_to_video_wan22_5B.json)

### 5.4 工作流二：5B 混合版 — 图生视频（I2V）

#### 模型节点配置

同 5.2 文生视频配置（共用同一 diffusion 模型）。

#### 操作步骤

1. 加载工作流
2. 在 `Load Image` 节点中上传初始帧图片（快捷键 `Ctrl+B` 启用该节点）
3. 在 `Wan22ImageToVideoLatent` 节点中调整尺寸和视频总帧数（`length`）
4. 在 `CLIP Text Encode` 节点中输入运动描述提示词
5. 点击 **Run** 执行生成

#### 工作流 JSON 下载

- [image_to_video_wan22_5B.json](https://comfyanonymous.github.io/ComfyUI_examples/wan22/image_to_video_wan22_5B.json)

### 5.5 工作流三：14B — 文生视频（T2V）

#### 模型节点配置

需要**两个** `Load Diffusion Model` 节点：

| 节点序号 | 加载文件 |
|----------|----------|
| 第 1 个 `Load Diffusion Model` | `wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors` |
| 第 2 个 `Load Diffusion Model` | `wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors` |
| `Load CLIP` | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` |
| `Load VAE` | `wan_2.1_vae.safetensors` |

#### 操作步骤

1. 加载工作流模板
2. 分别在两个 `Load Diffusion Model` 节点中加载高噪声和低噪声模型
3. 在 `EmptyHunyuanLatentVideo` 节点中调整尺寸和帧数
4. 编辑提示词
5. 点击 **Run** 执行生成

#### 工作流 JSON 下载

- [text_to_video_wan22_14B.json](https://comfyanonymous.github.io/ComfyUI_examples/wan22/text_to_video_wan22_14B.json)

### 5.6 工作流四：14B — 图生视频（I2V）

#### 模型节点配置

需要**两个** `Load Diffusion Model` 节点：

| 节点序号 | 加载文件 |
|----------|----------|
| 第 1 个 `Load Diffusion Model` | `wan2.2_i2v_high_noise_14B_fp16.safetensors` |
| 第 2 个 `Load Diffusion Model` | `wan2.2_i2v_low_noise_14B_fp16.safetensors` |
| `Load CLIP` | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` |
| `Load VAE` | `wan_2.1_vae.safetensors` |

#### 操作步骤

1. 加载工作流
2. 在 `Load Image` 节点上传作为初始帧的图像
3. 分别加载两个 diffusion 模型
4. 编辑提示词
5. 点击 **Run** 执行生成

#### 工作流 JSON 下载

- [image_to_video_wan22_14B.json](https://comfyanonymous.github.io/ComfyUI_examples/wan22/image_to_video_wan22_14B.json)

### 5.7 工作流五：14B — 首尾帧生成（FLF2V）

> **注意**：首尾帧工作流复用 I2V 模型文件，无需额外下载模型。

#### 操作步骤

1. 在第一个 `Load Image` 节点上传**起始帧**图片
2. 在第二个 `Load Image` 节点上传**结束帧**图片
3. 在 `WanFirstLastFrameToVideo` 节点中调整尺寸设置：
   - 默认使用较小尺寸以节省显存
   - 显存充足时可尝试 **720P 分辨率**
4. 根据首尾帧内容编写合适的提示词
5. 点击 **Run** 执行生成

#### 工作流 JSON 下载

- [video_wan2_2_14B_flf2v.json](https://raw.githubusercontent.com/Comfy-Org/workflow_templates/refs/heads/main/templates/video_wan2_2_14B_flf2v.json)

---

## 6. 低显存方案

如果 GPU 显存不足以运行原始精度模型，可使用以下替代方案：

### 6.1 GGUF 量化版本

| 资源 | 链接 | 说明 |
|------|------|------|
| Wan2.2-I2V-A14B-GGUF | [bullerwins/Wan2.2-I2V-A14B-GGUF](https://huggingface.co/bullerwins/Wan2.2-I2V-A14B-GGUF/) | 14B 图生视频量化版 |
| Wan2.2-T2V-A14B-GGUF | [bullerwins/Wan2.2-T2V-A14B-GGUF](https://huggingface.co/bullerwins/Wan2.2-T2V-A14B-GGUF) | 14B 文生视频量化版 |
| QuantStack GGUFs | [QuantStack/Wan2.2 GGUFs](https://huggingface.co/collections/QuantStack/wan22-ggufs-6887ec891bdea453a35b95f3) | 多种量化等级 |

**所需自定义节点**：[City96/ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF)

安装方式：
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/city96/ComfyUI-GGUF.git
cd ComfyUI-GGUF
pip install -r requirements.txt
```

### 6.2 4 步加速 LoRA（Lightx2v）

可在仅 4 步去噪迭代中生成视频，大幅降低计算量：

| 资源 | 链接 |
|------|------|
| Wan2.2-T2V-A14B-4steps-lora-rank64-V1 | [lightx2v/Wan2.2-Lightning](https://huggingface.co/lightx2v/Wan2.2-Lightning/tree/main/Wan2.2-T2V-A14B-4steps-lora-rank64-V1) |

### 6.3 WanVideoWrapper 替代方案

**自定义节点**：[Kijai/ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper)

**配套 fp8 模型**：[Kijai/WanVideo_comfy_fp8_scaled](https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled)

### 6.4 ComfyUI 原生 Offloading

ComfyUI 自带智能内存管理机制，会自动在显存不足时将模型临时卸载到系统内存，无需额外配置。只需确保：
- 系统内存（RAM）足够大（建议 ≥ 32GB）
- 使用最新版 ComfyUI

---

## 7. 常见问题排查

### 7.1 加载工作流时节点缺失

**可能原因：**
1. 未使用最新 ComfyUI 版本（需要 Nightly 版本）
2. 部分节点在启动时导入失败

**解决方案：**
- 更新至最新 Nightly 版本
- 检查控制台日志，查看具体哪个节点导入失败

### 7.2 桌面版找不到新核心节点

**原因：**
桌面版基于 ComfyUI 稳定版发布，新核心节点可能尚未包含。

**解决方案：**
- 等待下一个稳定版发布后自动更新
- 或切换到手动安装方式使用 Nightly 版本

### 7.3 "Torch not compiled with CUDA enabled" 错误

**解决方案：**
```bash
pip uninstall torch
# 重新安装对应 CUDA 版本的 PyTorch（参见 3.1 步骤 3）
pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu130
```

### 7.4 生成速度慢

**优化建议：**
- 确认 PyTorch CUDA 版本与 GPU 匹配
- 尝试使用 PyTorch Nightly 版本（可能有性能提升）
- 减少 `EmptyHunyuanLatentVideo` 中的帧数（`length`）
- 降低分辨率
- 使用 GGUF 量化版或 4 步 LoRA 加速

### 7.5 显存不足（OOM）

**解决方案：**
- 使用 ComfyUI 原生 offloading（自动生效）
- 切换到 GGUF 量化版本
- 使用 5B 模型替代 14B 模型
- 降低生成视频的分辨率和帧数
- 增大系统内存作为 offload 缓冲

### 7.6 AMD GPU 特殊设置

对于未被 ROCm 正式支持的 AMD 显卡：

```bash
# RDNA2 或更早 (6700, 6600 等)
HSA_OVERRIDE_GFX_VERSION=10.3.0 python main.py

# RDNA3 (7600 等)
HSA_OVERRIDE_GFX_VERSION=11.0.0 python main.py
```

ROCm 性能优化：
```bash
PYTORCH_TUNABLEOP_ENABLED=1 python main.py
```

---

## 8. 附录

### 8.1 模型版本对比总结

| 对比项 | 5B 混合版 | 14B T2V | 14B I2V | 14B FLF2V |
|--------|-----------|---------|---------|-----------|
| **功能** | 文生视频 + 图生视频 | 文生视频 | 图生视频 | 首尾帧生成 |
| **最低 VRAM** | 8 GB | 16 GB（建议） | 16 GB（建议） | 同 I2V |
| **Diffusion 模型数** | 1 个 | 2 个（高/低噪声） | 2 个（高/低噪声） | 同 I2V |
| **模型精度** | fp16 | fp8 scaled | fp16 | 同 I2V |
| **VAE 文件** | `wan2.2_vae` | `wan_2.1_vae` | `wan_2.1_vae` | 同 I2V |
| **架构** | 单模型 | MoE 双专家 | MoE 双专家 | 同 I2V |

### 8.2 推荐部署组合

#### 入门级（8GB VRAM）

```
模型选择：5B 混合版（TI2V）
功能：文生视频 + 图生视频
优势：单一模型，最低硬件需求
```

#### 标准级（16GB VRAM）

```
模型选择：14B T2V + 14B I2V
功能：文生视频 + 图生视频 + 首尾帧生成
优势：更高画质，电影级美学控制
注意：需要下载 4 个 diffusion 模型文件
```

#### 低显存优化级（8-12GB VRAM）

```
模型选择：GGUF 量化版 + ComfyUI-GGUF 自定义节点
功能：同 14B 版本，但显存占用大幅降低
优势：在有限显存下运行 14B 模型
```

### 8.3 相关链接汇总

| 资源 | 链接 |
|------|------|
| ComfyUI 仓库 | https://github.com/Comfy-Org/ComfyUI |
| Wan 2.2 ComfyUI Repackaged（ModelScope） | https://www.modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged |
| Wan 2.2 ComfyUI Repackaged（HuggingFace） | https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged |
| ComfyUI Wan 2.2 官方示例 | https://comfyanonymous.github.io/ComfyUI_examples/wan22/ |
| Comfy 官方文档 Wan 2.2 | https://docs.comfy.org/tutorials/video/wan/wan2_2 |
| Wan 2.2 原始仓库 | https://github.com/Wan-Video/Wan2.2 |
| ComfyUI 便携版下载 | https://github.com/comfyanonymous/ComfyUI/releases |
| ComfyUI 桌面版下载 | https://www.comfy.org/download |
| ComfyUI-GGUF 自定义节点 | https://github.com/city96/ComfyUI-GGUF |
| WanVideoWrapper 自定义节点 | https://github.com/kijai/ComfyUI-WanVideoWrapper |
| Lightx2v 4步 LoRA | https://huggingface.co/lightx2v/Wan2.2-Lightning |

---

> **文档版本**：v1.0 | **更新日期**：2026-07-08 | **适用 ComfyUI 版本**：≥ v0.27.0（推荐 Nightly）
