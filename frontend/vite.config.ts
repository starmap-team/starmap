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
  // ponytail: force pre-bundle 3d-graph deps to avoid "Failed to fetch
  // dynamically imported module" in Vite dev (three.js sub-path imports
  // aren't picked up by the dependency scanner at cold-start).
  optimizeDeps: {
    include: ['three', '3d-force-graph'],
  },
})
