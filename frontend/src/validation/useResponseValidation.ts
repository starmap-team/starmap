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
 * import positionSchema from '@contracts/schemas/position.schema.json'
 *
 * const { validateResponse } = useResponseValidation
 *
 * async function fetchPositions {
 * const raw = await request.get('/positions')
 * // schema 传整个文档（含 definitions/$defs），definitionPath 指定校验目标
 * return validateResponse(raw, positionSchema, '/positions', 'PositionListResponse')
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
 * @param schema - JSON Schema 文档（含 definitions/$defs，供 $ref 解析）
 * @param endpoint - API 端点名（用于日志）
 * @param definitionPath - 可选：definitions/$defs 中的模型名（如 "PositionListResponse"）；
 * 不传则直接校验传入的 schema
 * @returns 原始数据（附带类型守卫效果）
 */
  validateResponse: <T>(
    data: T,
    schema: JSONSchema | JSONSchemaProperty,
    endpoint?: string,
    definitionPath?: string,
  ) => T
}

/** 从文档 definitions/$defs 中查找模型定义 */
function lookupDefinition(
  doc: JSONSchema | JSONSchemaProperty,
  path: string,
): JSONSchemaProperty | undefined {
  const defsTable = doc as unknown as Record<string, Record<string, JSONSchemaProperty>>
  for (const key of ['definitions', '$defs']) {
    const defs = defsTable[key]
    if (defs && typeof defs === 'object' && path in defs) {
      return defs[path]
    }
  }
  return undefined
}

export function useResponseValidation(): UseResponseValidationReturn {
  function validateResponse<T>(
    data: T,
    schema: JSONSchema | JSONSchemaProperty,
    endpoint?: string,
    definitionPath?: string,
  ): T {
    let target: JSONSchema | JSONSchemaProperty = schema
    if (definitionPath) {
      const def = lookupDefinition(schema, definitionPath)
      if (def) target = def
 // definitionPath 不存在：降级为直接校验整个文档（不抛异常）
    }
    const result = validateSafe(data, target, schema as JSONSchema)

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
