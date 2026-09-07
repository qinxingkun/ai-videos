# H3 Studio

MiniMax-H3 本地测试台：文生 / 图生 / 首尾帧 / 参考多模态，参数可配，GPU 实时监控。

默认 UI 为 `web/`（静态页，由 FastAPI 一并托管）。`frontend/` 为可选 React/Vite 源码（需可访问 npm registry）。

## 依赖

- Python：`.venvs/minimax-h3`（FastAPI / httpx / uvicorn）
- 已启动的 SGLang H3：
  - FL2VA：`http://127.0.0.1:30010`（文生 / 首尾帧）
  - Ref2VA：`http://127.0.0.1:30011`（参考图/视频/音频，可选）

## 启动 H3 推理服务

```bash
# FL2VA（常用：GPU1）
bash /mnt/ddr2/qxk/workspace/ai-videos/scripts/start-minimax-h3-fl2va.sh

# Ref2VA（需空闲显存，默认 GPU0:30011）
bash /mnt/ddr2/qxk/workspace/ai-videos/h3-studio/scripts/start-minimax-h3-ref2va.sh
```

环境变量：`H3_FL2VA_URL`、`H3_REF2VA_URL`（默认如上）。

鉴权与 ComfyUI 节点共用：`MINIMAX_H3_API_TOKEN` 或 `.secrets/minimax_h3_api_token`。启动脚本会把它传给 SGLang `--api-key`。先跑：

```bash
bash /mnt/ddr2/qxk/workspace/ai-videos/scripts/init-minimax-h3-token.sh
```

## 启动 Studio（推荐）

```bash
source /mnt/ddr2/qxk/workspace/ai-videos/.venvs/minimax-h3/bin/activate
cd /mnt/ddr2/qxk/workspace/ai-videos/h3-studio/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8787
```

浏览器打开 `http://<host>:8787`。

一键脚本（API + 可选 Vite）：

```bash
bash /mnt/ddr2/qxk/workspace/ai-videos/h3-studio/scripts/dev.sh
```

## 功能

| 模式 | Upstream |
|------|----------|
| 文生 / 首帧 / 尾帧 / 首尾帧 | FL2VA |
| 参考图 / 参考视频 / 参考语音 / 混合参考 | Ref2VA |

约束：当前 H3 要求 `short_edge=768`，时长 4–15 秒。

上传：`data/uploads/`；结果缓存：`data/outputs/`。
