import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    hmr: { overlay: false },
    // PLAN-014: 允许导入仓库根下 starmap-contracts/ 的契约 JSON Schema
    fs: { allow: ['..'] },
    // 永久防护：dev 下禁止浏览器缓存模块，避免缓存到 optimizeDeps 重跑期的
    // 504 中间态导致"容器已起、页面空白"。强制每次重新拉取模块。
    headers: {
      'Cache-Control': 'no-store',
    },
    proxy: {
      '/api': {
        // Docker 网络: VITE_API_PROXY_TARGET=http://starmap-backend:8000
        // 本地开发: 回退到 http://localhost:8000
        target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        // ponytail: forward client IP so audit logs are traceable
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            const ip = req.socket.remoteAddress
            if (ip) proxyReq.setHeader('X-Forwarded-For', ip)
          })
        },
      },
    },
  },
  build: {
    // P3-5 fix: G6 v5 is ~1.4MB minified, which exceeds the default 500KB warning.
    // G6 is already split into its own chunk (vendor-g6) and lazy-loaded via dynamic import.
    // The size is inherent to the library; raising the limit suppresses the warning.
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-vue': ['vue', 'vue-router', 'pinia'],
          'vendor-echarts': ['echarts', 'vue-echarts'],
          'vendor-element': ['element-plus', '@element-plus/icons-vue'],
          'vendor-utils': ['axios'],
          'vendor-g6': ['@antv/g6'],
        },
      },
    },
  },
  // 3d-force-graph 的 three.js 深层子路径 import 在 dev 下需预打包，否则
  // 画布动态 import 报 "Failed to fetch dynamically imported module" 致 3D 空白。
  // 宿主 node_modules 可写后此预打包安全（此前匿名卷只读导致 EACCES 死循环）。
  optimizeDeps: {
    include: ['three', '3d-force-graph'],
  },
})
