/**
 * StarMap 前端校验层 — 统一入口。
 *
 * 功能：
 * - validate / validateSafe / validateOrThrow → JSON Schema 运行时校验
 * - parseErrorResponse / extractFieldErrors / buildErrorMessage → API 错误解析
 * - useFormValidation → 表单预提交校验
 * - useResponseValidation → API 响应数据结构校验
 */

export { validate, validateSafe, validateOrThrow } from './validate'
export type { ValidationResult } from './validate'

export { parseErrorResponse, extractFieldErrors, buildErrorMessage } from './errors'
export type { FieldErrorsMap } from './errors'

export { useFormValidation } from './useFormValidation'
export type { UseFormValidationOptions, UseFormValidationReturn } from './useFormValidation'

export { useResponseValidation } from './useResponseValidation'
export type { UseResponseValidationReturn } from './useResponseValidation'

export type { ErrorResponse, FieldError, PaginatedResponse, PaginationMeta, JSONSchema, JSONSchemaProperty } from './types'
