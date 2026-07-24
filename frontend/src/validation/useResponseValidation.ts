/**
 * API 响应数据校验 Composable。
 *
 * 在 Store 中接收后端 API 响应后，对数据结构进行校验，
 * 防止接口变更导致前端渲染异常。
 *
 * 设计原则：
 * - 校验失败**不阻断**业务流程（降级使用原始数据）
 * - 仅在开发环境 console.warn 输出差异
 * - 适用于所有 Store 的 API 调用模式的零侵入集成
 *
 * @example
 * ```ts
 * import { useResponseValidation } from '@/validation/useResponseValidation'
 * import positionListSchema from '@/validation/schemas/position.schema.json'
 *
 * const { validateResponse } = useResponseValidation()
 *
 * async function fetchPositions() {
 *   const raw = await request.get('/positions')
 *   const validated = validateResponse(raw, positionListSchema.definitions.PositionListResponse)
 *   positions.value = validated as PositionListResponse
 * }
 * ```
 */

import type { JSONSchema, JSONSchemaProperty } from './types'
import { validateSafe } from './validate'

export interface UseResponseValidationReturn {
  /**
   * 校验 API 响应数据。
   *
   * 校验失败时在 DEV 环境输出警告，但始终返回原始数据。
   * 这确保即使在生产环境 schema 不匹配也不会导致页面白屏。
   *
   * @param data - 后端返回的原始数据
   * @param schema - JSON Schema 定义
   * @param endpoint - API 端点名（用于日志）
   * @returns 原始数据（附带类型守卫效果）
   */
  validateResponse: <T>(data: T, schema: JSONSchema | JSONSchemaProperty, endpoint?: string) => T
}

export function useResponseValidation(): UseResponseValidationReturn {
  function validateResponse<T>(
    data: T,
    schema: JSONSchema | JSONSchemaProperty,
    endpoint?: string,
  ): T {
    const result = validateSafe(data, schema)

    if (!result.valid && import.meta.env.DEV) {
      const label = endpoint ? `[${endpoint}]` : ''
      console.groupCollapsed(
        `⚠️ 响应数据校验失败 ${label} — ${result.errors.length} 个字段不匹配`,
      )
      for (const err of result.errors) {
        console.warn(`  ${err.field}: ${err.message} (code: ${err.code})`)
      }
      console.groupEnd()
    }

    return data
  }

  return { validateResponse }
}
