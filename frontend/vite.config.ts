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
    allowedHosts: ['localhost', '127.0.0.1', 'frontend', 'starmap-frontend', 'host.docker.internal'],
    proxy: {
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
  },
})
