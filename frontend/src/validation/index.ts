/**
 * StarMap 前端校验层 — 统一入口。
 *
 * 功能：
 * - validate / validateSafe / validateOrThrow → JSON Schema 运行时校验
 * - parseErrorResponse / extractFieldErrors / buildErrorMessage → API 错误解析
 * - useResponseValidation → API 响应数据结构校验
 *
 * 注：useFormValidation 于 (audit 2026-08-15) 删除 —— 全代码库
 * 0 调用点。后端 Pydantic 强校验 + useResponseValidation 已足够。
 */

export { validate, validateSafe, validateOrThrow } from './validate'
export type { ValidationResult } from './validate'

export { parseErrorResponse, extractFieldErrors, buildErrorMessage } from './errors'
export type { FieldErrorsMap } from './errors'

export { useResponseValidation } from './useResponseValidation'
export type { UseResponseValidationReturn } from './useResponseValidation'

export type { ErrorResponse, FieldError, PaginatedResponse, PaginationMeta, JSONSchema, JSONSchemaProperty } from './types'
