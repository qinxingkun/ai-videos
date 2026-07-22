import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const API_HOST = process.env.API_HOST || process.env.TOOL_API_HOST || 'http://127.0.0.1:8190'
const COMFYUI_HOST = process.env.COMFYUI_HOST || 'http://127.0.0.1:8188'
const DEV_PORT = Number(process.env.PORT || process.env.VITE_PORT || 5173)

export default defineConfig({
  plugins: [vue()],
  server: {
    // 监听 IPv6（Linux 上通常同时接受 IPv4），修复 localhost → ::1 连接被拒绝
    host: '::',
    port: DEV_PORT,
    strictPort: true,
    // 规避 ENOSPC（系统 inotify watch 上限不足）
    watch: {
      usePolling: true,
      interval: 1000
    },
    proxy: {
      '/v1': { target: API_HOST, changeOrigin: true, timeout: 0, proxyTimeout: 0 },
      '/health': { target: API_HOST, changeOrigin: true, timeout: 0, proxyTimeout: 0 },
      // 可选：ComfyUI 直连调试
      '/system_stats': { target: COMFYUI_HOST, changeOrigin: true },
      '/ws': {
        target: COMFYUI_HOST.replace(/^http/, 'ws'),
        ws: true,
        changeOrigin: true
      }
    }
  }
})
