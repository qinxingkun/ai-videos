# ai-videos

基于 **ComfyUI + Wan 2.2 / LTX 2.3** 的 AI 视频生成 monorepo，包含短剧生成 Web 应用、配音口型 Provider、视频拼接工具，以及上游模型/推理依赖。

> 根目录：`/mnt/ddr2/qxk/workspace/ai-videos`

---

## 目录

1. [项目概览](#1-项目概览)
2. [系统架构](#2-系统架构)
3. [目录结构](#3-目录结构)
4. [子项目说明](#4-子项目说明)
5. [硬件与环境要求](#5-硬件与环境要求)
6. [快速启动](#6-快速启动)
7. [服务端口一览](#7-服务端口一览)
8. [配置说明](#8-配置说明)
9. [测试与验证](#9-测试与验证)
10. [Git 与 .gitignore](#10-git-与-gitignore)
11. [文档索引](#11-文档索引)
12. [常见问题](#12-常见问题)

---

## 1. 项目概览

| 属性 | 说明 |
|------|------|
| **定位** | AI 短剧 / 多分镜视频生成 + 配音口型 + 后期拼接 |
| **主应用** | `wan22-demo`（Vue 3 前端 + FastAPI 后端） |
| **推理引擎** | `ComfyUI`（调度 Wan 2.2 / LTX 2.3 工作流） |
| **配音** | `CosyVoice 3`（TTS + ASR 质检） |
| **口型** | `LatentSync 1.6`（选择性 ROI 口型同步） |
| **辅助工具** | `video-concat`（独立视频拼接 + 配音 UI） |

核心能力：

- **T2V / I2V / FLF2V**：单段最长约 5 秒（Wan 2.2 为主，LTX 2.3 可选）
- **多分镜短剧**：30s（6×5s）/ 90s（20×5s）链式生成、角色圣经、末帧接力
- **角色一致性**：InstantID 定妆、VACE 参考引导、ArcFace 质检、Animate 兜底
- **Wan 配音**：多人指定说话人、FaceAtlas 绑定、LatentSync 选择性口型、QA 质检
- **媒体处理**：抽帧、smart-splice、RIFE 接缝插帧、历史记录

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户 / 浏览器                                  │
└───────────────┬──────────────────────────────┬──────────────────────────┘
                │ :5173                         │ :5180
                ▼                               ▼
┌───────────────────────┐           ┌───────────────────────┐
│  wan22-demo/frontend  │           │  video-concat (Vue)   │
│  Vue 3 + Vite         │           │  视频拼接 + 配音 UI    │
└───────────┬───────────┘           └───────────┬───────────┘
            │ :8190 REST API                     │ :3040 Express
            ▼                                    │
┌───────────────────────┐                        │
│  wan22-demo/backend │◄───────────────────────┘
│  FastAPI            │      CosyVoice TTS
└───────────┬───────────┘
            │ ComfyUI API (:8188)
            ▼
┌───────────────────────┐     ┌───────────────────────┐
│  ComfyUI              │     │  Provider 层           │
│  Wan / LTX 工作流      │     │  CosyVoice  :8191     │
│  custom_nodes         │     │  LatentSync :8192     │
└───────────────────────┘     └───────────────────────┘
            │
            ▼
    ComfyUI/models/（推理权重，git 不跟踪）
    CosyVoice/pretrained_models/、LatentSync/checkpoints/（Provider 权重，git 不跟踪）
```

**数据流（多分镜生成）**：

1. 前端提交多分镜任务 → 后端按段调用 ComfyUI 工作流
2. 每段末帧作为下一段条件图（可选 VACE / InstantID / Animate 增强）
3. smart-splice 拼接视觉母版 → CosyVoice 合成台词 → LatentSync 口型 → 混音输出

---

## 3. 目录结构

```
ai-videos/
├── README.md                 # 本文档
├── .gitignore                # 排除模型、媒体、日志等大文件
│
├── wan22-demo/               # ★ 主应用
│   ├── frontend/             #   Vue 3 前端
│   ├── backend/              #   FastAPI 后端
│   ├── deployment/           #   启动脚本、Provider、systemd、日志
│   └── docs/                 #   PRD、部署文档、SOP
│
├── ComfyUI/                  # ★ 推理引擎（含 models/、custom_nodes/）
├── CosyVoice/                # ★ TTS Provider 源码 + 预训练模型
├── LatentSync/               # ★ 口型同步 Provider 源码 + checkpoint
├── video-concat/             #   独立视频拼接工具
│
├── Wan2.2/                   #   Wan 官方模型代码（上游）
```

### 路径约定

后端通过**相对路径**定位 sibling 目录（无需硬编码绝对路径）：

| 配置项 | 默认路径（相对 `wan22-demo/`） |
|--------|-------------------------------|
| `comfyui_root` | `../ComfyUI` |
| `insightface_root` | `../LatentSync/checkpoints/auxiliary` |
| CosyVoice 模型 | `../CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B` |
| Whisper checkpoint | `../LatentSync/checkpoints/whisper/tiny.pt` |

---

## 4. 子项目说明

### 4.1 wan22-demo（主应用）

| 组件 | 技术栈 | 说明 |
|------|--------|------|
| `frontend/` | Vue 3 + Vite | 视频生成 UI、多分镜编辑器、配音时间轴 |
| `backend/` | FastAPI + uvicorn | REST API、工作流构建、媒体/配音编排 |
| `backend/workflows/` | ComfyUI API JSON | t2v / i2v / flf2v / vace / instantid 等工作流 |
| `deployment/` | Bash + systemd | 一键启停、Provider 适配器 |

详见 [`wan22-demo/README.md`](wan22-demo/README.md)。

### 4.2 ComfyUI（推理引擎）

- 官方 ComfyUI + 视频相关 custom nodes：
  - `ComfyUI-WanVideoWrapper`
  - `ComfyUI-VideoHelperSuite`
  - `ComfyUI-Frame-Interpolation`（RIFE 接缝插帧）
  - `ComfyUI_InstantID`（定妆照）
- 模型权重位于 `ComfyUI/models/`（约 200GB+，**不纳入 git**）
- 输入/输出：`ComfyUI/input/`、`ComfyUI/output/video/`

### 4.3 CosyVoice（TTS）

- Fun-CosyVoice 3 零样本语音合成
- HTTP 适配器：`wan22-demo/deployment/providers/cosyvoice_server.py`
- 参考音色：`wan22-demo/backend/data/voices/*.wav`
- 同时提供 ASR 转写接口（配音 QA 用）

### 4.4 LatentSync（口型同步）

- LatentSync 1.6，512×512 口型扩散
- HTTP 适配器：`wan22-demo/deployment/providers/latentsync_server.py`
- 支持多人 ROI 选择性口型 + SyncNet QA
- **注意**：默认 `start-all-gpu1.sh` 不启动 LatentSync，需手动或 systemd 启动

### 4.5 video-concat（视频拼接）

- 独立的 Vue + Express 工具
- 上传多段视频 → ffmpeg 拼接 → 可选 CosyVoice 配音
- 与 wan22-demo 功能部分重叠，保留作快速后期工具

### 4.6 实验 / 未接入项目

| 目录 | 说明 | 状态 |
|------|------|------|
| `JoyAI-Echo/` | 分钟级多镜头音视频联合生成 | 已克隆，未接入 wan22-demo |
| `ComfyUI_JoyAI_Echo/` | JoyAI 的 ComfyUI 节点 | 同上 |
| `MuseTalk/` | 腾讯口型同步 | 备选，未接入 |
| `GPT-SoVITS/` | 少样本 TTS | 备选，未接入 |
| `Wan2.2/` | Wan 官方推理代码 | 参考 / 独立实验 |

---

## 5. 硬件与环境要求

### 5.1 硬件

| 组件 | 最低要求 | 推荐 |
|------|---------|------|
| GPU | NVIDIA ≥ 16GB VRAM | RTX 6000 / A100 80GB |
| 磁盘 | ≥ 300GB 可用（含模型） | NVMe SSD |
| 内存 | ≥ 32GB | 64GB+ |

### 5.2 Conda 环境

本机使用 miniconda 隔离各 Provider 依赖：

| 环境 | 用途 | Python 路径 |
|------|------|-------------|
| `comfyui` | ComfyUI 推理 | `/home/hik/miniconda3/envs/comfyui/bin/python` |
| `cosyvoice` | CosyVoice TTS | `/home/hik/miniconda3/envs/cosyvoice/bin/python` |
| `latentsync` | LatentSync 口型 | `/home/hik/miniconda3/envs/latentsync/bin/python` |

`wan22-demo/backend` 使用独立 venv（轻量 FastAPI 依赖）：

```bash
cd wan22-demo/backend
python3 -m venv .venv
env -u http_proxy -u https_proxy .venv/bin/pip install -r requirements.txt
```

> **迁移注意**：目录移动后若 venv 报 `ModuleNotFoundError`，需按上面命令重建 venv。

### 5.3 Node.js

- `wan22-demo/frontend` 和 `video-concat` 均需 `npm install`
- Node.js ≥ 18 推荐

---

## 6. 快速启动

### 6.1 一键启动（GPU1，推荐）

```bash
cd /mnt/ddr2/qxk/workspace/ai-videos/wan22-demo/deployment
./start-all-gpu1.sh
```

启动内容：

| 服务 | 端口 |
|------|------|
| ComfyUI | 8188 |
| wan22 后端 | 8190 |
| wan22 前端 | 5173 |
| CosyVoice | 8191 |
| video-concat API | 3040 |
| video-concat UI | 5180 |

停止：

```bash
./stop-all-gpu1.sh
```

日志目录：`wan22-demo/deployment/logs/gpu1-all/`

### 6.2 启动 LatentSync（配音口型必需）

`start-all-gpu1.sh` **不包含** LatentSync。需要配音功能时额外启动：

```bash
/home/hik/miniconda3/envs/latentsync/bin/python \
  wan22-demo/deployment/providers/latentsync_server.py \
  --latentsync-root /mnt/ddr2/qxk/workspace/ai-videos/LatentSync \
  --port 8192
```

或使用 systemd（路径已更新至 `ai-videos/`）：

```bash
systemctl --user enable wan22-demo/deployment/systemd/wan22-latentsync.service
systemctl --user start wan22-latentsync
```

### 6.3 手动分步启动（开发调试）

```bash
# 终端 1：ComfyUI
cd ai-videos/ComfyUI
/home/hik/miniconda3/envs/comfyui/bin/python main.py --listen 0.0.0.0 --port 8188

# 终端 2：后端
cd ai-videos/wan22-demo/backend
source .venv/bin/activate
env NO_PROXY=127.0.0.1,localhost PORT=8190 python main.py

# 终端 3：前端
cd ai-videos/wan22-demo/frontend
npm run dev
```

### 6.4 首次配置

```bash
# 1. 后端环境变量
cp wan22-demo/backend/.env.example wan22-demo/backend/.env

# 2. 前端依赖
cd wan22-demo/frontend && npm install
cd ../../video-concat && npm install

# 3. 确认 ComfyUI 模型已就位（见部署文档）
ls ComfyUI/models/diffusion_models/
```

---

## 7. 服务端口一览

| 端口 | 服务 | 健康检查 |
|------|------|---------|
| 8188 | ComfyUI | `GET /system_stats` |
| 8190 | wan22 后端 | `GET /health` |
| 8191 | CosyVoice | `GET /health` |
| 8192 | LatentSync | `GET /health` |
| 5173 | wan22 前端 | 浏览器访问 |
| 3040 | video-concat API | `GET /api/health` |
| 5180 | video-concat UI | 浏览器访问 |
| 8192 | Qwen-Image（可选） | 独立脚本 `start-qwen-image.sh` |

完整健康检查（含所有 Provider）：

```bash
curl -s http://127.0.0.1:8190/health/full | python3 -m json.tool
```

全部 `ok: true` 需要 LatentSync 也在运行。

---

## 8. 配置说明

### 8.1 后端环境变量

文件：`wan22-demo/backend/.env`（从 `.env.example` 复制）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `COMFYUI_URL` | `http://127.0.0.1:8188` | ComfyUI 地址 |
| `COSYVOICE_URL` | `http://127.0.0.1:8191/synthesize` | TTS 合成 |
| `ASR_QA_URL` | `http://127.0.0.1:8191/transcribe` | ASR 质检 |
| `LATENTSYNC_URL` | `http://127.0.0.1:8192/lipsync` | 口型同步 |
| `SYNCNET_QA_URL` | `http://127.0.0.1:8192/sync-qa` | 口型 QA |
| `LIPSYNC_PROVIDER_MODE` | `preferred` | `off` / `preferred` / `required` |
| `TTS_PROVIDER_MODE` | `required` | 同上 |

路径类配置默认通过 sibling 目录自动解析，一般无需手动设置 `COMFYUI_ROOT`。

### 8.2 代理设置

若系统配置了 `HTTP_PROXY`（如 `127.0.0.1:7890`），**必须**对本地服务设置 bypass，否则后端无法探测 ComfyUI/CosyVoice：

```bash
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost
```

`start-all-gpu1.sh` 已内置此设置。手动启动后端时同样需要。

### 8.3 GPU 选择

`start-all-gpu1.sh` 默认 `CUDA_VISIBLE_DEVICES=1`（GPU1）。修改脚本或通过环境变量覆盖：

```bash
CUDA_VISIBLE_DEVICES=0 ./start-all-gpu1.sh
```

---

## 9. 测试与验证

### 9.1 后端单元测试

```bash
cd wan22-demo/backend
env -u http_proxy -u https_proxy .venv/bin/pytest -q
# 预期：77 passed
```

### 9.2 前端单元测试

```bash
cd wan22-demo/frontend
npm test
# 预期：18 passed
```

### 9.3 API 冒烟

```bash
cd wan22-demo/backend
env NO_PROXY=127.0.0.1,localhost .venv/bin/python scripts/smoke_api.py
# 预期：SMOKE PASSED
```

### 9.4 Provider 健康（需 LatentSync 运行）

```bash
env NO_PROXY=127.0.0.1,localhost RUN_REAL_DUB_SMOKE=1 \
  .venv/bin/pytest -q tests/test_provider_smoke.py
```

### 9.5 前端构建

```bash
cd wan22-demo/frontend
npm run build
```

### 9.6 一键自检清单

```bash
# 所有服务端口
ss -ltn | rg ':8188|:8190|:8191|:8192|:5173|:3040|:5180'

# 路径正确性
curl -s http://127.0.0.1:8190/health | python3 -m json.tool
# comfyuiRoot 应为 .../ai-videos/ComfyUI

# 完整链路
curl -s http://127.0.0.1:8190/health/full | python3 -m json.tool
```

---

## 10. Git 与 .gitignore

本仓库为 **monorepo**，根目录 `ai-videos/.gitignore` 排除大文件，仅跟踪源码与配置。

### 排除内容

| 类别 | 示例 |
|------|------|
| 模型权重 | `*.safetensors`, `*.ckpt`, `*.pth`, 各项目内 `models/`、`checkpoints/`、`pretrained_models/` |
| 生成媒体 | `output/`, `uploads/`, `*.mp4`, `*.wav` |
| 运行时 | `node_modules/`, `.venv/`, `*.log`, `deployment/logs/` |
| 本地数据 | `.env`, `dubbing_sessions/`, `voices/`, `characters.json` |

### 常用 git 操作

```bash
cd /mnt/ddr2/qxk/workspace/ai-videos

# 查看将被跟踪的文件
git add -n . | head -50

# 首次提交
git add .
git status
git commit -m "Initial ai-videos monorepo"
```

> 子项目原有的独立 git 历史已在合并时移除。如需跟踪上游更新，可改用 git submodule 或文档记录 remote URL。

---

## 11. 文档索引

| 文档 | 路径 | 内容 |
|------|------|------|
| 产品需求（PRD） | [`wan22-demo/docs/AI视频生成平台需求文档.md`](wan22-demo/docs/AI视频生成平台需求文档.md) | 功能需求、里程碑 |
| Wan 2.2 部署 | [`wan22-demo/docs/ComfyUI_Wan2.2_部署文档.md`](wan22-demo/docs/ComfyUI_Wan2.2_部署文档.md) | 模型下载、ComfyUI 配置 |
| 角色一致性 SOP | [`wan22-demo/docs/FACE_CONSISTENCY_SOP.md`](wan22-demo/docs/FACE_CONSISTENCY_SOP.md) | InstantID / VACE / Animate |
| ComfyUI API | [`wan22-demo/docs/COMFYUI_API.md`](wan22-demo/docs/COMFYUI_API.md) | ComfyUI REST 接口 |
| wan22-demo 详情 | [`wan22-demo/README.md`](wan22-demo/README.md) | API、功能开关、配音流程 |
| ComfyUI 使用 | [`ComfyUI/docs/ComfyUI使用文档.md`](ComfyUI/docs/ComfyUI使用文档.md) | ComfyUI 操作指南 |

---

## 12. 常见问题

### Q: 迁移目录后服务启动失败？

**A:** 两个常见原因：

1. **venv 失效** — 目录移动后 shebang 指向旧路径，重建 venv：
   ```bash
   cd wan22-demo/backend && rm -rf .venv
   python3 -m venv .venv
   env -u http_proxy -u https_proxy .venv/bin/pip install -r requirements.txt
   ```

2. **旧进程占用** — 迁移前启动的进程仍持有旧 inode。先 `./stop-all-gpu1.sh`，再重新启动。

### Q: `/health/full` 显示 ComfyUI/CosyVoice 离线，但 curl 直接访问正常？

**A:** 系统 `HTTP_PROXY` 导致 Python httpx 走代理访问 localhost 失败。设置：
```bash
export NO_PROXY=127.0.0.1,localhost
```
然后重启后端。

### Q: 模型找不到？

**A:** 检查 `ComfyUI/models/` 下是否有对应权重，参考 [`ComfyUI_Wan2.2_部署文档.md`](wan22-demo/docs/ComfyUI_Wan2.2_部署文档.md)。CosyVoice / LatentSync 权重分别在各自项目的 `pretrained_models/`、`checkpoints/` 目录。

### Q: 单段生成很慢？

**A:** Wan LightX2V 首段约 4–5 分钟，后续段约 40s–2min/5s，属正常范围。

### Q: 配音功能不可用？

**A:** 确认 CosyVoice（:8191）和 LatentSync（:8192）均已启动，且 `backend/.env` 中 Provider URL 正确。参考 [`wan22-demo/README.md`](wan22-demo/README.md) 配音章节。

### Q: IDE 仍打开旧路径下的文件？

**A:** 迁移后旧路径 `workspace/wan22-demo/` 可能只剩 vite 缓存残留。请改用 `ai-videos/wan22-demo/` 下的文件。可删除 workspace 根目录下的空壳目录：
```bash
rm -rf /mnt/ddr2/qxk/workspace/wan22-demo
rm -rf /mnt/ddr2/qxk/workspace/video-concat
```

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-21 | 从 `workspace/` 根目录迁移至 `ai-videos/` monorepo；新增 `.gitignore`；更新 deployment/systemd 路径 |
