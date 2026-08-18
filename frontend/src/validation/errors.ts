/**
 * API 错误响应解析工具。
 *
 * 从 Axios 错误中提取结构化的 ErrorResponse，
 * 将字段级错误映射到表单字段，支持前端逐字段高亮。
 */

import type { AxiosError } from 'axios'
import type { ErrorResponse } from './types'

/** 字段路径 → 错误信息映射（用于表单错误状态） */
export type FieldErrorsMap = Map<string, { message: string; code: string }>

/**
 * 从 Axios 错误中提取 ErrorResponse。
 * 支持旧格式 `{detail: "..."}` 和新格式 `{detail, code, timestamp, fields}`。
 */
export function parseErrorResponse(error: AxiosError): ErrorResponse | null {
  const data = error.response?.data
  if (!data || typeof data !== 'object') return null

  const resp = data as Record<string, unknown>

 // 新格式：已有 detail + code
  if (typeof resp.detail === 'string' && typeof resp.code === 'string') {
    return resp as unknown as ErrorResponse
  }

 // 旧格式兼容：{detail: "..."}
  if (typeof resp.detail === 'string') {
    return {
      detail: resp.detail,
      code: 'UNKNOWN',
      timestamp: new Date().toISOString(),
    }
  }

  return null
}

/**
 * 从错误响应中提取字段级错误映射。
 *
 * @returns Map<字段路径, {message, code}>
 *
 * @example
 * ```ts
 * const fieldErrors = extractFieldErrors(error)
 * // Map { "password" → { message: "密码长度不能少于 8 个字符", code: "min_length" } }
 * ```
 */
export function extractFieldErrors(error: AxiosError): FieldErrorsMap {
  const map: FieldErrorsMap = new Map()
  const errResp = parseErrorResponse(error)
  if (!errResp?.fields) return map

  for (const fe of errResp.fields) {
 // 合并同一字段的多条错误（取第一条，或拼接）
    map.set(fe.field, { message: fe.message, code: fe.code })
  }

  return map
}

/**
 * 构建面向用户的错误摘要消息。
 *
 * 优先级：服务端 detail > 字段错误摘要 > HTTP 状态码消息 > 通用 fallback
 */
export function buildErrorMessage(error: AxiosError, defaultMsg = '操作失败，请稍后重试'): string {
  const errResp = parseErrorResponse(error)

 // 优先使用服务端 detail
  if (errResp?.detail && errResp.detail !== '请求数据校验失败') {
    return errResp.detail
  }

 // 校验错误：汇总字段级错误
  if (errResp?.fields?.length) {
    const first = errResp.fields[0]
    const remaining = errResp.fields.length - 1
    if (remaining > 0) {
      return `${first.message}（还有 ${remaining} 个字段存在问题）`
    }
    return first.message
  }

 // 降级：HTTP 状态码
  const status = error.response?.status
  const STATUS_MESSAGES: Record<number, string> = {
    400: '请求参数有误，请检查后重试',
    401: '登录已过期，请重新登录',
    403: '没有权限执行此操作',
    404: '请求的资源不存在',
    409: '数据存在冲突，请刷新后重试',
    422: '数据校验失败，请检查输入',
    429: '请求过于频繁，请稍后重试',
    500: '服务器内部错误，请稍后重试',
    502: '服务暂时不可用，请稍后重试',
    503: '服务维护中，请稍后重试',
  }
  if (status) return STATUS_MESSAGES[status] ?? `请求失败 (${status})`

  if (!navigator.onLine) return '网络连接已断开，请检查网络设置'
  return defaultMsg
}
