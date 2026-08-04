import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/__tests__/**/*.test.ts', 'src/**/__tests__/**/*.spec.ts'],
    exclude: [
      'node_modules',
      'dist',
      'e2e/**',
      'cypress/**',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.ts', 'src/**/*.vue'],
      exclude: [
        'node_modules',
        'dist',
        'src/**/*.d.ts',
        'src/**/__tests__/**',
        'src/**/*.test.ts',
        'src/**/*.spec.ts',
        'src/main.ts',
        'src/env.d.ts',
      ],
      thresholds: {
        lines: 20,
        functions: 15,
        branches: 10,
        statements: 20,
      },
    },
  },
})
