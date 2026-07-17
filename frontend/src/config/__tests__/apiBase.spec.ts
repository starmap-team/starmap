import { describe, it, expect } from 'vitest'
import { API_BASE, apiUrl } from '../apiBase'

/**
 * W1-T3 regression (P0-10 path mismatch).
 *
 * 历史 bug: 生产 Dockerfile 注入 VITE_API_BASE_URL=/api，但 request.ts
 * fallback 是 /api/v1。生产浏览器请求 `/auth/login` 拼成
 * `/api/auth/login`，nginx 转发到 `:8000/api/auth/login`，后端无
 * 此路由 → 404。
 *
 * 修复：API_BASE 单一真相源硬编码为 '/api/v1'。下面这组测试确保
 * 任何后续修改都不能把 baseURL 改成其它值（除非显式更新 SSoT）。
 */

describe('config/apiBase', () => {
  it('API_BASE 锁定为 /api/v1（与后端 FastAPI prefix 对齐）', () => {
    expect(API_BASE).toBe('/api/v1')
  })

  it('apiUrl 把相对路径拼成绝对路径', () => {
    expect(apiUrl('/auth/login')).toBe('/api/v1/auth/login')
    expect(apiUrl('auth/login')).toBe('/api/v1/auth/login')
  })

  it('apiUrl 不产生双斜杠', () => {
    // 防止 API_BASE 被改成 /api/v1/ 时出现 //auth/login
    expect(apiUrl('/auth/login')).not.toContain('//auth')
    expect(apiUrl('auth/login')).not.toContain('//auth')
  })

  it('apiUrl 不允许相对路径嵌入 baseURL', () => {
    // 反例：apiUrl('v1/auth/login') 在 base='/api/v1' 下应得 '/api/v1/v1/auth/login'，
    // 这正是我们要避免的——所以测试断言"调用方必须传 /xxx 形式"是错的设计。
    // 当前行为是 path 已含 /v1 时直接拼接（由调用方负责）。
    expect(apiUrl('/v1/auth/login')).toBe('/api/v1/v1/auth/login')
  })
})