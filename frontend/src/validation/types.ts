/**
 * 前端校验类型定义 — 与后端 app/schemas/common.py 完全一致。
 *
 * 这些类型同时用于：
 * - API 错误响应的结构化解析
 * - 表单校验的错误提示
 * - 编译期类型检查
 */

/** 字段级校验错误 */
export interface FieldError {
 /** 出错字段路径，嵌套用 '.' 分隔，数组用 '[n]' 索引 */
  field: string
 /** 接收到的问题值（生产环境为 null） */
  value: unknown
 /** 面向用户的错误描述 */
  message: string
 /** 机器可读错误码 */
  code: string
}

/** 统一 API 错误响应 */
export interface ErrorResponse {
 /** 面向用户的错误摘要 */
  detail: string
 /** 机器可读错误码 */
  code: string
 /** 错误发生时间 (ISO 8601 UTC) */
  timestamp: string
 /** 字段级错误详情（仅校验错误时存在） */
  fields?: FieldError[]
 /** 内部诊断（仅 DEV 环境返回） */
  _internal_detail?: string
}

/** 分页元信息 */
export interface PaginationMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

/** 泛型分页响应 */
export interface PaginatedResponse<T> {
  items: T[]
  pagination: PaginationMeta
}

// ── JSON Schema 类型（子集，仅用于运行时校验） ──

export interface JSONSchemaProperty {
  type?: string | string[]
  description?: string
  title?: string
  minLength?: number
  maxLength?: number
  minimum?: number
  maximum?: number
  pattern?: string
  format?: string
  enum?: (string | number)[]
  items?: JSONSchemaProperty
  properties?: Record<string, JSONSchemaProperty>
  required?: string[]
  additionalProperties?: boolean
  default?: unknown
 /** 文档内引用，如 "#/$defs/SkillNode"（按根文档 $defs/definitions 解析） */
  $ref?: string
}

export interface JSONSchema {
  $schema?: string
  title?: string
  description?: string
  type?: string
  properties?: Record<string, JSONSchemaProperty>
  required?: string[]
  definitions?: Record<string, JSONSchemaProperty>
 /** Pydantic v2 导出的引用定义表（refs 指向 "#/$defs/X"） */
  $defs?: Record<string, JSONSchemaProperty>
}
