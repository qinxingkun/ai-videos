# wan22-demo 前端

Vue 3 + Vite。经 REST（`/v1/*`）调用后端，不直连 ComfyUI。

```bash
# 先启动后端：cd ../backend && python main.py
cd frontend
npm install
npm run dev      # :5173
npm run build
```

环境变量：`API_HOST`（默认 `http://127.0.0.1:8190`）控制 Vite 代理。
