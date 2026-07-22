# wan22-demo

LTX 2.3 / Wan 2.2 AI 短剧生成演示：**FastAPI 后端** + **Vue 3 前端**，经 REST API 调度本地 **ComfyUI**。

## 目录结构

```
wan22-demo/
├── frontend/                 # Vue 3 + Vite（:5173）
│   ├── src/
│   └── package.json
├── backend/                  # FastAPI（:8190）
│   ├── app/                  # API / services / schemas
│   ├── scripts/              # CLI：冒烟、媒体、工作流、对话测试
│   ├── tests/
│   ├── workflows/            # ComfyUI API 工作流 JSON
│   ├── data/                 # 角色库、fixtures
│   ├── main.py
│   └── requirements.txt
├── docs/
└── README.md
```

## 快速启动

```bash
# 前端依赖
cd frontend && npm install

# 后端依赖
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 终端 1：ComfyUI
cd ../ComfyUI && python main.py --listen 0.0.0.0 --port 8188

# 终端 2：后端
cd ai-videos/wan22-demo/backend && source .venv/bin/activate && python main.py

# 终端 3：前端
cd ai-videos/wan22-demo/frontend && npm run dev
```

| 变量 | 默认 | 说明 |
|------|------|------|
| `COMFYUI_URL` | `http://127.0.0.1:8188` | ComfyUI 地址 |
| `COMFYUI_ROOT` | `<ai-videos>/ComfyUI` | 输入/输出目录 |
| `API_HOST` | `http://127.0.0.1:8190` | 前端 Vite 代理目标 |

## API 概览

文档：http://127.0.0.1:8190/docs ，详见 [backend/README.md](backend/README.md)。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/v1/videos/t2v` | 文生视频 |
| `POST` | `/v1/videos/i2v` | 图生视频 |
| `POST` | `/v1/videos/flf2v` | 首尾帧生视频 |
| `GET` | `/v1/videos/tasks/{id}` | 查询任务 |
| `POST` | `/v1/media/upload` | 上传图片 |
| `GET` | `/v1/media/view` | 查看媒体 |
| `GET` | `/v1/characters` | 角色库 |

```bash
curl -s http://127.0.0.1:8190/v1/videos/t2v \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"a cat","engine":"ltx"}'
```

## 测试

```bash
# 单元 + 媒体集成测试
cd backend && .venv/bin/pytest -q

# API 冒烟（需先 python main.py）
cd backend && .venv/bin/python scripts/smoke_api.py

# 对话 prompt 校验
cd backend && .venv/bin/python scripts/verify_dialogue_test_case.py

# 提交对话测试第 1 段（需后端 + ComfyUI）
cd backend && .venv/bin/python scripts/submit_dialogue_test_shot.py
```

## 功能

- **T2V / I2V**：以 **Wan 2.2** 为主（LTX 2.3 可选）；**单段最长 5s**
- **多分镜短剧**：时长预设 **约 30s（6×5s）** / **约 90s（20×5s）**；链式末帧、角色圣经；LTX 另支持 FLF2V / 对白
- **媒体**：抽帧、smart-splice 拼接、质检、角色库

## 生产质量增强（角色一致性 / 连贯性）

针对多分镜长链（尤其 90s/20 段预设）人设漂移、接缝重复/鬼影的四阶段质量方案，全部为**生成质量算法层**开关，默认对旧行为向后兼容：

| 阶段 | 能力 | 开关 / 阈值 | 说明 |
|------|------|------------|------|
| 一 | 角色圣经校验 + 防漂移负向提示 | `characterBible.js` 必填字段校验；负向提示自动追加 `ANTI_DRIFT_NEGATIVE` | 缺字段仅 UI 警告，不阻断 |
| 一 | 镜头语法警告 | `shotGrammar.js` | 连续雷同景别时提示，不阻断生成 |
| 一 | 锚点刷新节奏 + 软拉回混合 | `durationPresets.js` 的 `anchorRefreshEvery` / `anchorBlendWeight`；90s 预设默认每 5 段刷新、混合权重 0.22 | 用 ComfyUI 内置 `ImageBlend` 节点，`blend_factor=0` 时完全向后兼容 |
| 一 | 运动感知接缝选点 | `analyze-splice` 的 `motionSearchWindow` | 在名义裁切点窗口内选运动最小帧作为真实切点 |
| 二 | 人脸一致性质检 | `referenceImageName` + `identityThreshold`（默认 `0.32`，见 `DEFAULT_IDENTITY_THRESHOLD`） | 基于 `insightface`（ArcFace，纯推理）；依赖/参考图缺失时自动 `skipped`，不阻断 |
| 二 | 无脸门控 | `POST /v1/media/detect-face`；多分镜抽帧后自动 | 末帧无人脸 → 下一段条件图回退定妆照 |
| 一/主路径 | InstantID 定妆照 | `POST /v1/images/lookbook` | SDXL + InstantID；产出供 VACE/Animate `ref_images` |
| 一/主路径 | Wan-VACE 参考引导 | I2V 请求 `use_vace=true` + `ref_image_name` | `workflows/vace_i2v.api.json`；需 VACE 模块 + Wan2.1 T2V |
| 二 | 自愈重试环 | 每段最多重试 2 次（`MAX_SELF_HEAL_RETRIES`）：先 seed 偏移+提高锚点权重，再强制 FLF2V/锚点拉回；末次可触发 Animate | 仍不达标则中止，交由"重试该段"人工介入 |
| 二 | 质检可视化 | `MultiShotEditor.vue` 分段质检得分表 | 人脸相似度 / 无脸回退 / 接缝运动分 / Animate / QA issues |
| 三 | 接缝微观插帧 | UI 开关"接缝微观插帧"（`seamInterp` / `seamInterpFrames`，默认关闭） | 基于 ComfyUI-Frame-Interpolation（RIFE），需通过 ComfyUI Manager 安装；未安装/失败自动回退 micro-xfade |
| 四（可选） | 关键镜头 Animate 兜底 | UI 开关（默认关闭，默认首尾两段）；**在 VACE/I2V + ArcFace 之后** | 1280×720 @ 16fps×81；详见 [docs/FACE_CONSISTENCY_SOP.md](docs/FACE_CONSISTENCY_SOP.md) |

新增依赖（阶段二/三/四）：
- Python：`insightface`、`onnxruntime`、`opencv-python-headless`（见 `backend/requirements.txt`，CPU 推理即可）
- ComfyUI 自定义节点：`ComfyUI-Frame-Interpolation`（阶段三）、`ComfyUI-WanVideoWrapper` + `ComfyUI-VideoHelperSuite`（阶段四，身份锁定重渲染工作流用到其 `VHS_LoadVideo`/`VHS_VideoCombine`）

已在本机验证安装并跑通真实推理（非 mock），关键安装细节：

| 组件 | 安装方式 | 落地路径 | 备注 |
|------|---------|---------|------|
| ComfyUI-Frame-Interpolation | `git clone` 到 `custom_nodes/`（GitHub 直连不稳定时可用镜像如 `https://gh-proxy.com/https://github.com/...`） | `custom_nodes/ComfyUI-Frame-Interpolation` | RIFE 权重 `rife47.pth` 需从 HuggingFace 镜像（`hf-mirror.com`）下载到 `ckpts/rife/`，节点自带的 GitHub Release 直连下载在国内网络下大概率会拿到损坏文件 |
| ComfyUI-VideoHelperSuite | 同上 `git clone` | `custom_nodes/ComfyUI-VideoHelperSuite` | 阶段四工作流依赖，容易被漏装 |
| ComfyUI-WanVideoWrapper | 同上 `git clone` | `custom_nodes/ComfyUI-WanVideoWrapper` | Python 依赖用 `pip install --no-deps` 逐个补齐（`ftfy`/`accelerate`/`diffusers`/`peft`/`protobuf`/`pyloudnorm`/`gguf`/`wcwidth`），避免误升级已装好的 `torch`/`transformers` |
| Wan2.2-Animate 权重 | `Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors`（约 17.3GB，新卡用 e4m3fn，老卡用 e5m2 变体） | `models/diffusion_models/` | 来自 `Kijai/WanVideo_comfy_fp8_scaled` 仓库 `Wan22Animate/` 目录，HuggingFace 直连不通时用 `hf-mirror.com` 镜像 |
| T5 文本编码器（WanVideoWrapper 专用） | `umt5-xxl-enc-fp8_e4m3fn.safetensors`（约 6.7GB） | `models/text_encoders/` | **注意**：不能复用 ComfyUI 原生的 `umt5_xxl_fp8_e4m3fn_scaled.safetensors`（"scaled fp8" 格式），`LoadWanVideoT5TextEncoder` 节点会直接报错拒绝加载，需单独下载 Kijai 仓库里的非 scaled 版本 |
| VAE / 主 T2V/I2V 权重 | 无需额外下载 | 复用已有 `wan_2.1_vae.safetensors` | Wan2.2 系列复用 Wan2.1 的 VAE |

另外，验证阶段三时发现并修复了 `seam_interp.py` 里一处真实 bug：ffmpeg 的 `-vsync vfr` 与显式 `-r <fps>` 同时使用在部分 ffmpeg 版本上会报 "contradictory" 而拼接失败（此前一直被 `try/except` 悄悄吞掉未被发现），已移除 `-vsync vfr`。

## Wan 成片配音

Wan 多分镜可在 Smart Splice 后生成统一的 25fps CFR / PTS0 视觉母版，再按 48kHz PCM 时间轴合成台词、选择性处理近景口型、混音并一次性编码 AAC。后端接口为 `POST /v1/media/dub`；LTX 流程不调用该接口。

独立的 Wan **T2V 5s / I2V 5s** 页面也提供配音开关：可填写台词、参考声线 `voiceId`、25fps 起止帧和 `off/preferred/required` 口型策略。配音在原始视频生成完成后执行，最终结果区与历史记录保存的是带音轨成片；刷新页面恢复生成任务时会继续执行已保存的配音配置。

### 多人指定说话人

多人画面采用两阶段生产流程，避免 LatentSync 默认选择“最大脸”而驱动错人：

1. `POST /v1/media/dub/analyze` 先生成 RIFE 25fps 视觉母版，使用 InsightFace/SCRFD + ArcFace 建立稳定 `FaceAtlas`，再按角色定妆照自动绑定 `speakerId → faceTrackId`。
2. 自动绑定低于阈值或存在歧义时返回 `awaiting_binding`，前端展示每条轨道的代表帧和可见率，用户人工确认后调用 `POST /v1/media/dub/render`。
3. 每句台词使用结构化 `utterance`（`speakerId/text/startFrame/endFrame/lipSyncPolicy`），首版严格禁止时间重叠；按目标轨道动态裁剪单脸 ROI，完成 LatentSync 后只回贴目标脸区域。
4. QA 按句检查目标脸 SyncNet、ASR、轨道可见率、身份保持和非目标区域变化。`preferred` 失败会恢复该句原画面并记录降级，`required` 失败会阻断成片。

会话 manifest 和 FaceAtlas 缓存在 `backend/data/dubbing_sessions/`，默认保留 72 小时，可从 `analyzing / awaiting_binding / rendering` 阶段恢复。中间拼接音频使用无损编码，配音中间音频统一为 PCM，最终只进行一次 AAC 编码。

CosyVoice 3 与 LatentSync 1.6 使用独立 Python 环境。HTTP 适配器位于 `deployment/providers/`，对应的 systemd 用户服务模板位于 `deployment/systemd/`。复制 `backend/.env.example` 为 `backend/.env` 后，按实际端口配置 `COSYVOICE_URL` 与 `LATENTSYNC_URL`。CosyVoice 的 `voiceId` 是 `backend/data/voices/` 下的参考音频文件名；未配置真实 provider 时，`required` 策略会阻断成片，`preferred` 会在 QA 中明确记录降级，不会伪装成已完成口型同步。

配音成片会检查 25fps、视频 PTS0、最终帧数、48kHz 音轨、AAC 解码后的 PCM 样本数、一帧以内的音画时长误差、H.264/AAC/yuv420p 全片解码兼容性与 EBU R128 响度。配置 `ASR_QA_URL` 后校验台词内容，配置 `SYNCNET_QA_URL` 后校验口型置信度和偏移；`required` 口型未配置 SyncNet QA 会阻断输出。关键路径不使用 `-shortest` 或 `aresample=async=1`。

真实 provider 发版前可运行 `backend/scripts/smoke_dub_providers.py`；传入 `--video` 和 `--audio` 时会同时执行一次真实 LatentSync 推理。`/health/full` 会检查 ComfyUI、CosyVoice、LatentSync、ASR 和 SyncNet 服务。

## 常见问题

- **未连接到后端**：确认 `cd backend && python main.py`（:8190）
- **模型找不到**：检查 ComfyUI `models/` 与 workflow 文件名
- **单段超时**：Wan LightX2V 首段约 4–5 分钟、后续约 40 秒–2 分钟/5s 段
- **生成 90s**：Wan 多分镜页选「约 90 秒（20×5s）」；不靠加长单段（上限仍为 5s）
