# wan22-demo FastAPI 后端

REST API：视频生成、媒体处理、角色库。纯 Python（含 ffmpeg 媒体管线）。

## 启动

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python main.py
# → http://127.0.0.1:8190/docs
```

## 目录

```
backend/
├── app/           # FastAPI 应用
├── scripts/       # CLI 工具与冒烟测试
├── tests/         # pytest
├── workflows/     # ComfyUI 工作流 JSON
├── data/          # characters.json、fixtures
├── main.py
└── requirements.txt
```

## 测试

```bash
.venv/bin/pytest -q
.venv/bin/python scripts/smoke_api.py              # 需本服务已启动
.venv/bin/python scripts/verify_dialogue_test_case.py
```

更多 CLI 见 [scripts/README.md](scripts/README.md)。
