# 人脸一致性 SOP（InstantID + Wan-VACE + Animate）

## 流水线总览

```
参考脸 → InstantID 定妆照/段首帧
       → Wan-VACE（ref_images=定妆照）分段 5s
       → ArcFace 质检 + 自愈
       → 关键镜 / 质检失败 → Wan2.2-Animate relock 兜底
       → Smart Splice / 配音
```

| 阶段 | 技术 | 职责 | 本机路径 |
|------|------|------|----------|
| 0 | InstantID | 造身份资产（定妆照/首帧） | `custom_nodes/ComfyUI_InstantID` + `models/instantid/` + `models/controlnet/instantid_controlnet.safetensors` + `models/insightface/models/antelopev2/` |
| 1 | Wan-VACE | 生成时参考图锁身份 | `Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors` + `Wan2_1-T2V-14B_fp8_e4m3fn.safetensors`；工作流 `workflows/vace_i2v.api.json` |
| 2 | ArcFace | 段级身份质检 / 自愈触发 | `character_qa.check_identity_similarity` → `POST /v1/media/validate/segment` |
| 3 | Wan2.2-Animate | **VACE 之后**关键镜或 QA 失败兜底 | `workflows/postprocess/animate_relock.api.json`，**1280×720 @ 16fps × 81 帧**（与 Wan 多分镜一致） |

## 无脸末帧硬规则

```
if 末帧无人脸:
  VACE.ref_images = 定妆照（必须）
  下一段条件图回退定妆照（face-gate）；末帧不当身份源
else:
  VACE.ref_images = 定妆照（必须）
  末帧可作为 start/input_frames 辅助场景连续
```

## Animate relock 策略（阶段 3）

1. **时机**：仅在 VACE/I2V 初渲完成且（可选）时长规范之后；**默认不抢在质检前**。
2. **触发**：
   - UI 勾选「关键镜头身份锁定」→ 默认首尾两段在 VACE 出片后跑 Animate；
   - 自愈环耗尽后仍身份不达标 → 强制尝试一次 Animate 再终检。
3. **分辨率对齐**：驱动视频与输出统一 **1280×720**、**16 fps**、**81 帧**，与 Wan 5s 段一致；勿再用 832×480。
4. **参考图**：始终用 InstantID 定妆照（`referenceImageName`），勿用无脸末帧。
5. **失败回退**：Animate 未安装/超时/报错 → `applied=false`，保留 VACE 初渲，不阻断拼接。

## API 入口

| 能力 | 接口 |
|------|------|
| InstantID 定妆照 | `POST /v1/images/lookbook`（`face_image_name` + `prompt`） |
| VACE 参考引导 I2V | `POST /v1/videos/i2v` 且 `engine=wan` + `vace=true`（或 `mode`/`use_vace`） |
| 段质检（含身份） | `POST /v1/media/validate/segment` + `referenceImageName` + `identityThreshold` |
| Animate 兜底 | `POST /v1/media/animate-relock` |

## VRAM 注意

VACE-14B 与 Animate-14B 不宜与 Qwen/VLLM 同卡满载；分段排队。权重可用 `hf-mirror.com` + `hf download`。
