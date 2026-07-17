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
      // Default → http://localhost:8000 (matches docker-compose.dev.yml backend mapping 8000:8000).
      // Override via VITE_API_BASE_URL when running backend on a different host/port.
      // UAT fallback: when running frontend as a docker-compose service, point at
      // the docker-network host. `starmap-backend-prod` is the backend service name.
      // In dev (vite on host), proxy stays at http://localhost:8000 because the
      // host's port 8000 maps to backend container's 8000.
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
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
    exclude: [
      'node_modules',
      'dist',
      'e2e/**',
      'cypress/**',
    ],
  },
})
