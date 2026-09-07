# ai-videos

基于 **ComfyUI + Wan 2.2 / LTX 2.3** 的 AI 视频生成 monorepo；另含 **MiniMax-H3** 本地试验链路（Studio / 导演台插件）。覆盖短剧多分镜生成、配音口型、后期拼接，以及上游模型与备选 Provider。

> 根目录：`/mnt/ddr2/qxk/workspace/ai-videos`  
> GitHub：`https://github.com/qinxingkun/ai-videos`  
> 内网 GitLab（自行同步）：`https://innovation-gitlab.hikvision.com.cn/HiStor/preresearch/ai-video`

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
11. [文档说明](#11-文档说明)
12. [常见问题](#12-常见问题)

---

## 1. 项目概览

| 属性 | 说明 |
|------|------|
| **定位** | AI 短剧 / 多分镜视频生成 + 配音口型 + 后期拼接；并行预研 MiniMax-H3 |
| **主应用（Wan 链路）** | `wan22-demo`（Vue 3 + FastAPI） |
| **推理引擎** | `ComfyUI`（Wan 2.2 / LTX 2.3 工作流） |
| **配音** | `CosyVoice 3`（TTS + ASR 质检） |
| **口型** | `LatentSync 1.6`（选择性 ROI 口型同步） |
| **辅助工具** | `video-concat`（独立视频拼接 + 配音 UI） |
| **H3 试验** | `MiniMax-H3` + `h3-studio` + `ComfyUI_MiniMaxH3_Director` |

**Wan 主链路能力：**

- **T2V / I2V / FLF2V**：单段最长约 5 秒（Wan 2.2 为主，LTX 2.3 可选）
- **多分镜短剧**：30s（6×5s）/ 90s（20×5s）链式生成、角色圣经、末帧接力
- **角色一致性**：InstantID 定妆、VACE 参考引导、ArcFace 质检、Animate 兜底
- **Wan 配音**：多人指定说话人、FaceAtlas 绑定、LatentSync 选择性口型、QA 质检
- **媒体处理**：抽帧、smart-splice、RIFE 接缝插帧、历史记录

**MiniMax-H3 试验能力（未并入 wan22-demo）：**

- 文生 / 图生 / 首尾帧（FL2VA）、参考多模态（Ref2VA）
- 单段约 4–15 秒、原生立体声；本地 Studio UI + ComfyUI 导演台插件

---

## 2. 系统架构

### 2.1 Wan 主链路（生产可用）

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
│  wan22-demo/backend   │◄───────────────────────┘
│  FastAPI              │      CosyVoice TTS
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

**数据流（多分镜生成）：**

1. 前端提交多分镜任务 → 后端按段调用 ComfyUI 工作流
2. 每段末帧作为下一段条件图（可选 VACE / InstantID / Animate 增强）
3. smart-splice 拼接视觉母版 → CosyVoice 合成台词 → LatentSync 口型 → 混音输出

### 2.2 MiniMax-H3 试验链路

```
浏览器 :8787  →  h3-studio (FastAPI)
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  FL2VA :30010            Ref2VA :30011
  (文生/首尾帧)            (参考图/视频/音频)
        │
        └── 权重与代码：MiniMax-H3/
            ComfyUI 导演台：ComfyUI_MiniMaxH3_Director/
            辅助脚本：scripts/start-minimax-h3-*.sh 等
```

---

## 3. 目录结构

```
ai-videos/
├── README.md                      # 本文档
├── .gitignore                     # 排除模型、媒体、日志、docs/、密钥等
├── scripts/                       # H3 / ComfyUI 辅助脚本
│
├── wan22-demo/                    # ★ Wan 主应用
│   ├── frontend/                  #   Vue 3 前端
│   ├── backend/                   #   FastAPI 后端
│   └── deployment/                #   启停脚本、Provider、systemd
│
├── ComfyUI/                       # ★ 推理引擎（models/、custom_nodes/ 本地）
├── CosyVoice/                     # ★ TTS Provider
├── LatentSync/                    # ★ 口型同步 Provider
├── video-concat/                  #   独立视频拼接工具
│
├── MiniMax-H3/                    #   H3 上游模型与推理代码
├── h3-studio/                     #   H3 本地测试台
├── ComfyUI_MiniMaxH3_Director/    #   H3 ComfyUI 导演台插件（嵌套 git）
│
├── Wan2.2/                        #   Wan 官方推理代码（参考）
├── wan22_houmo/                   #   Wan2.2 后摩芯片量化部署示例
├── JoyAI-Echo/                    #   分钟级多镜头音视频（备选）
├── MuseTalk/                      #   腾讯口型（备选）
├── GPT-SoVITS/                    #   少样本 TTS（备选）
├── huobao-drama/                  #   第三方短剧平台（嵌套 git）
│
├── docs/                          #   本地技术方案文档（不进 git）
├── .secrets/                      #   本地密钥（不进 git）
└── .venvs/                        #   本地虚拟环境（不进 git）
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

- 官方 ComfyUI + 视频相关 custom nodes（如 WanVideoWrapper、VideoHelperSuite、Frame-Interpolation、InstantID 等）
- 模型权重位于 `ComfyUI/models/`（约 200GB+，**不纳入 git**）
- `custom_nodes/` 为本地安装目录（权重类文件仍被 ignore）
- 输入/输出：`ComfyUI/input/`、`ComfyUI/output/video/`

### 4.3 CosyVoice（TTS）

- Fun-CosyVoice 3 零样本语音合成
- HTTP 适配器：`wan22-demo/deployment/providers/cosyvoice_server.py`
- 参考音色：`wan22-demo/backend/data/voices/*.wav`（本地数据，不进 git）
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

### 4.6 MiniMax-H3 相关

| 目录 | 说明 | 状态 |
|------|------|------|
| `MiniMax-H3/` | 上游全模态音视频生成（FL2VA / Ref2VA 等） | 本地推理代码已纳入仓库；权重不进 git |
| `h3-studio/` | 本地测试台（参数可配、GPU 监控），默认 `:8787` | 可用，依赖已启动的 SGLang H3 服务 |
| `ComfyUI_MiniMaxH3_Director/` | ComfyUI 多段导演台插件 | 嵌套 git 仓库；按插件方式装到 ComfyUI |
| `scripts/` | 下载权重、初始化 Token、启动 FL2VA 等 | 见脚本内注释 |

启动 Studio 前需先起 H3 推理服务，例如：

```bash
bash scripts/init-minimax-h3-token.sh
bash scripts/start-minimax-h3-fl2va.sh
# 然后
source .venvs/minimax-h3/bin/activate
cd h3-studio/backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8787
```

详见 [`h3-studio/README.md`](h3-studio/README.md)、[`MiniMax-H3/README.zh-CN.md`](MiniMax-H3/README.zh-CN.md)。

### 4.7 参考 / 备选 / 实验

| 目录 | 说明 | 状态 |
|------|------|------|
| `Wan2.2/` | Wan 官方推理代码 | 参考；主链路走 ComfyUI |
| `wan22_houmo/` | Wan2.2 A14B 后摩芯片量化部署示例 | 独立实验 |
| `JoyAI-Echo/` | 分钟级多镜头音视频联合生成 | 已入库源码，未接入 wan22-demo |
| `MuseTalk/` | 腾讯实时口型 | 备选（当前用 LatentSync） |
| `GPT-SoVITS/` | 少样本克隆 TTS | 备选（当前用 CosyVoice） |
| `huobao-drama/` | 第三方 AI 短剧全流程平台 | 嵌套 git；与主链路独立 |

---

## 5. 硬件与环境要求

### 5.1 硬件

| 组件 | 最低要求 | 推荐 |
|------|---------|------|
| GPU | NVIDIA ≥ 16GB VRAM | RTX 6000 / A100 80GB |
| 磁盘 | ≥ 300GB 可用（含模型） | NVMe SSD |
| 内存 | ≥ 32GB | 64GB+ |

### 5.2 Conda / venv 环境

本机常用隔离环境：

| 环境 | 用途 | 说明 |
|------|------|------|
| `comfyui` | ComfyUI 推理 | miniconda env |
| `cosyvoice` | CosyVoice TTS | miniconda env |
| `latentsync` | LatentSync 口型 | miniconda env |
| `.venvs/minimax-h3` | h3-studio 后端 | 仓库内 venv（不进 git） |
| `wan22-demo/backend/.venv` | FastAPI 后端 | 项目内 venv（不进 git） |

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

### 6.1 一键启动 Wan 链路（GPU1，推荐）

```bash
cd /mnt/ddr2/qxk/workspace/ai-videos/wan22-demo/deployment
./start-all-gpu1.sh
```

| 服务 | 端口 |
|------|------|
| ComfyUI | 8188 |
| wan22 后端 | 8190 |
| wan22 前端 | 5173 |
| CosyVoice | 8191 |
| video-concat API | 3040 |
| video-concat UI | 5180 |

停止：`./stop-all-gpu1.sh`  
日志：`wan22-demo/deployment/logs/gpu1-all/`

### 6.2 启动 LatentSync（配音口型必需）

`start-all-gpu1.sh` **不包含** LatentSync：

```bash
/home/hik/miniconda3/envs/latentsync/bin/python \
  wan22-demo/deployment/providers/latentsync_server.py \
  --latentsync-root /mnt/ddr2/qxk/workspace/ai-videos/LatentSync \
  --port 8192
```

或使用 systemd（见 `wan22-demo/deployment/systemd/`）。

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
cp wan22-demo/backend/.env.example wan22-demo/backend/.env
cd wan22-demo/frontend && npm install
cd ../../video-concat && npm install
ls ComfyUI/models/diffusion_models/
```

### 6.5 MiniMax-H3 Studio（可选）

见 [4.6](#46-minimax-h3-相关) 与 [`h3-studio/README.md`](h3-studio/README.md)。

---

## 7. 服务端口一览

| 端口 | 服务 | 健康检查 |
|------|------|---------|
| 8188 | ComfyUI | `GET /system_stats` |
| 8190 | wan22 后端 | `GET /health` |
| 8191 | CosyVoice | `GET /health` |
| 8192 | LatentSync | `GET /health` |
| 5173 | wan22 前端 | 浏览器 |
| 3040 | video-concat API | `GET /api/health` |
| 5180 | video-concat UI | 浏览器 |
| 8787 | h3-studio | 浏览器 |
| 30010 | MiniMax-H3 FL2VA | SGLang / OpenAI 兼容 API |
| 30011 | MiniMax-H3 Ref2VA | 同上（可选） |

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

若系统配置了 `HTTP_PROXY`，**必须**对本地服务设置 bypass：

```bash
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost
```

`start-all-gpu1.sh` 已内置此设置。

### 8.3 GPU 选择

`start-all-gpu1.sh` 默认 `CUDA_VISIBLE_DEVICES=1`。可覆盖：

```bash
CUDA_VISIBLE_DEVICES=0 ./start-all-gpu1.sh
```

### 8.4 MiniMax-H3 鉴权

与 ComfyUI H3 节点共用：`MINIMAX_H3_API_TOKEN` 或 `.secrets/minimax_h3_api_token`（`.secrets/` 不进 git）。初始化：

```bash
bash scripts/init-minimax-h3-token.sh
```

---

## 9. 测试与验证

### 9.1 后端单元测试

```bash
cd wan22-demo/backend
env -u http_proxy -u https_proxy .venv/bin/pytest -q
```

### 9.2 前端单元测试

```bash
cd wan22-demo/frontend && npm test
```

### 9.3 API 冒烟

```bash
cd wan22-demo/backend
env NO_PROXY=127.0.0.1,localhost .venv/bin/python scripts/smoke_api.py
```

### 9.4 Provider 健康（需 LatentSync）

```bash
env NO_PROXY=127.0.0.1,localhost RUN_REAL_DUB_SMOKE=1 \
  .venv/bin/pytest -q tests/test_provider_smoke.py
```

### 9.5 一键自检

```bash
ss -ltn | rg ':8188|:8190|:8191|:8192|:5173|:3040|:5180|:8787'
curl -s http://127.0.0.1:8190/health/full | python3 -m json.tool
```

---

## 10. Git 与 .gitignore

### 远程与同步流程

| Remote | URL |
|--------|-----|
| `origin`（主） | `https://github.com/qinxingkun/ai-videos.git` |
| `gitlab`（可选） | `https://innovation-gitlab.hikvision.com.cn/HiStor/preresearch/ai-video.git` |

推荐流程：先推 GitHub，再在可访问内网的机器上拉取后推到 GitLab。

```bash
# 本机 → GitHub（需 PAT 或 SSH）
./scripts/push-to-github.sh
# 或：export GH_TOKEN=ghp_xxxx && ./scripts/push-to-github.sh

# 另一台能访问内网的机器：
git clone https://github.com/qinxingkun/ai-videos.git
cd ai-videos
git remote add gitlab https://innovation-gitlab.hikvision.com.cn/HiStor/preresearch/ai-video.git
git push -u gitlab main
```

### 排除内容（不进仓库）

| 类别 | 示例 |
|------|------|
| 模型权重 | `*.safetensors`, `*.ckpt`, `*.pth`, `models/`, `checkpoints/`, `pretrained_models/` |
| 生成媒体 | `output/`, `uploads/`, `*.mp4`, `*.wav` 等 |
| 运行时 | `node_modules/`, `.venv/`, `*.log`, `deployment/logs/` |
| 本地数据 | `.env`, `dubbing_sessions/`, `voices/`, `characters.json` |
| 密钥 | `.secrets/`, `secrets/` |
| **文档目录** | **`**/docs/`（全部 docs 目录仅本地保留）** |
| 压缩包 / 缓存 | `*.zip`, `*.tar.gz`, HF/ModelScope cache 等 |

### 嵌套仓库说明

`huobao-drama/`、`ComfyUI_MiniMaxH3_Director/` 目录内自带 `.git`，本 monorepo 中以 **gitlink** 形式记录，不会把其内部 `node_modules` 等一并提交。需要完整源码时请进入子目录单独操作，或改为 submodule。

---

## 11. 文档说明

**仓库内可阅读：**

| 文档 | 路径 |
|------|------|
| 本文档 | [`README.md`](README.md) |
| wan22-demo | [`wan22-demo/README.md`](wan22-demo/README.md) |
| h3-studio | [`h3-studio/README.md`](h3-studio/README.md) |
| MiniMax-H3（中文） | [`MiniMax-H3/README.zh-CN.md`](MiniMax-H3/README.zh-CN.md) |
| Wan2.2 上游 | [`Wan2.2/README.md`](Wan2.2/README.md) |

**仅本地、不进 git（`**/docs/`）：**

- 根目录 `docs/`：技术方案、预研报告、PDF 等
- `wan22-demo/docs/`：PRD、部署文档、SOP、ComfyUI API 说明等
- 各上游项目自带 `docs/`

克隆仓库后若需要这些文档，请从本地备份或内网文档库单独获取。

---

## 12. 常见问题

### Q: 推送到 Hikvision GitLab 失败（无法解析主机）？

**A:** `innovation-gitlab.hikvision.com.cn` 通常仅公司内网可达。请先推到 GitHub，再在能访问内网的机器上 `clone` / `pull` 后推到 GitLab（见 [10. Git 与 .gitignore](#10-git-与-gitignore)）。

### Q: 迁移目录后服务启动失败？

**A:** 常见原因：

1. **venv 失效** — 重建 `wan22-demo/backend/.venv`
2. **旧进程占用** — 先 `./stop-all-gpu1.sh` 再启动

### Q: `/health/full` 显示离线，但 curl 直接访问正常？

**A:** `HTTP_PROXY` 导致访问 localhost 走代理。设置 `NO_PROXY=127.0.0.1,localhost` 后重启后端。

### Q: 模型找不到？

**A:** 检查 `ComfyUI/models/`、`CosyVoice/pretrained_models/`、`LatentSync/checkpoints/`。权重不进 git，需本机另行下载。

### Q: 单段生成很慢？

**A:** Wan LightX2V 首段约 4–5 分钟，后续段约 40s–2min/5s，属正常范围。

### Q: 配音功能不可用？

**A:** 确认 CosyVoice（:8191）和 LatentSync（:8192）均已启动，且 `backend/.env` 中 Provider URL 正确。

### Q: 为什么克隆后没有 docs？

**A:** 根 `.gitignore` 使用 `**/docs/`，文档仅本地保留，不会出现在远程仓库中。

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-09-07 | 同步 monorepo：纳入 MiniMax-H3 / h3-studio / JoyAI-Echo 等；`**/docs/` 与 `.secrets/` 不进 git；先推 GitHub，再自行同步内网 GitLab |
| 2026-07-21 | 从 `workspace/` 根目录迁移至 `ai-videos/` monorepo；新增 `.gitignore`；更新 deployment/systemd 路径 |
