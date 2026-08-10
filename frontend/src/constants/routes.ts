/**
 * 应用路由路径常量 — 页面跳转的唯一事实源。
 * 与 `src/router/index.ts` 的 path 定义保持一致。
 */
export const APP_ROUTES = {
  HOME: '/',
  POSITIONS: '/positions',
  POSITION_DETAIL: (name: string) => `/position/${encodeURIComponent(name)}`,
  MATCH: '/match',
  EVOLUTION: '/evolution',
  QUALITY: '/quality',
  PIPELINE: '/pipeline',
  DATASOURCES: '/datasources',
  ANALYSIS: '/analysis',
  EXTRACT: '/extract',
  LOOP: '/loop',
  LOGIN: '/login',
  CHANGE_PASSWORD: '/change-password',
  ADMIN: '/admin',
  DASHBOARD: '/dashboard',
  LEARNING: '/learning',
} as const
