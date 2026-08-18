/**
 * 单一 API base URL 真相源（SSoT）。
 *
 * 修复（ 路径冲突）：
 * - 后端 `app.main:144` 把所有 router 挂在 `/api/v1` 下
 * - 历史遗留：前端构建期注入 `VITE_API_BASE_URL=/api`（Dockerfile），
 * 但 request.ts 缺省值是 `/api/v1`，导致生产浏览器请求
 * `POST /api/auth/login` 拼成 `/api/auth/login`，nginx 反代到
 * `:8000/api/auth/login`，后端无此路由 → 404。
 *
 * 现在前端 baseURL 与后端 prefix 强一致，不再依赖环境变量：
 * - nginx 已升级为 `proxy_pass ...:8000/api/v1/`（ 同步修改）
 * - Dockerfile 不再注入 VITE_API_BASE_URL（构建期常量已无用）
 * - dev 模式下 vite 代理 `/api` 仍转 `:8000`，到后端还是 `/api/v1/*`，
 * 因此 API_BASE='/api/v1' 在 dev / prod 行为一致。
 *
 * 禁止：任何其它文件写 `import.meta.env.VITE_API_BASE_URL || '/api/v1'`。
 * 如未来需要切换环境，请修改此处常量（保持 SSoT）。
 */
export const API_BASE = '/api/v1' as const

/**
 * 拼接相对路径到完整 URL。
 * 用法：`apiUrl('/auth/login')` → `/api/v1/auth/login`
 * 注意：返回相对路径，浏览器/Nginx/axios 各自负责域名解析。
 */
export function apiUrl(path: string): string {
 // 防御：避免双斜杠或 baseURL 重复
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE}${normalized}`
}