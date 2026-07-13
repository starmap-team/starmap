import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import charsetPlugin from './plugins/charset-plugin'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), charsetPlugin()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // 默认指向 8002（dev 端口：当前激活的 FastAPI 后端）。
      // 8000 是 docker-compose 默认端口，可能与 IDE 启动的开发后端并存；
      // 8002 是 docker-compose.dev.yml 中 backend-dev 服务的映射端口。
      // 可通过环境变量 VITE_API_BASE_URL 覆盖。
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8002',
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-vue': ['vue', 'vue-router', 'pinia'],
          'vendor-echarts': ['echarts', 'vue-echarts'],
          'vendor-element': ['element-plus', '@element-plus/icons-vue'],
          'vendor-utils': ['axios', 'lodash-es', '@vueuse/core'],
          'vendor-g6': ['@antv/g6'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
