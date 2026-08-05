/**
 * 轻量级 JSON Schema 运行时校验器。
 *
 * 零外部依赖，支持：
 * - 必填字段检查
 * - 类型检查 (string/number/integer/boolean/array/object)
 * - 字符串长度约束 (minLength/maxLength)
 * - 数值范围约束 (minimum/maximum)
 * - 正则匹配 (pattern)
 * - 嵌套对象递归校验
 * - 数组元素递归校验
 *
 * 用于：
 * - 前端表单预提交校验（即时反馈）
 * - API 响应数据结构校验（防接口变更异常）
 */

import type { FieldError, JSONSchema, JSONSchemaProperty } from './types'

/** 单次校验结果 */
export interface ValidationResult {
  valid: boolean
  errors: FieldError[]
}

function fail(field: string, message: string, code: string, value?: unknown): FieldError {
  return { field, value: value ?? null, message, code }
}

// ── $ref 解析 ──

/**
 * 解析文档内 JSON Pointer 引用（如 "#/$defs/SkillNode"、"#/definitions/X"）。
 * 解析失败返回 undefined（调用方按"悬空引用静默跳过"处理，与容错原则一致）。
 */
function resolveRef(ref: string, root: JSONSchema): JSONSchemaProperty | undefined {
  if (!ref.startsWith('#')) return undefined
  const parts = ref
    .slice(1)
    .split('/')
    .filter(Boolean)
    .map(p => p.replace(/~1/g, '/').replace(/~0/g, '~'))
  let cur: unknown = root
  for (const part of parts) {
    if (typeof cur !== 'object' || cur === null) return undefined
    cur = (cur as Record<string, unknown>)[part]
  }
  return typeof cur === 'object' && cur !== null ? (cur as JSONSchemaProperty) : undefined
}

// ── 核心校验函数 ──

function validateValue(
  value: unknown,
  schema: JSONSchemaProperty,
  path: string,
  errors: FieldError[],
  root: JSONSchema,
): void {
  if (value === undefined || value === null) {
    return // required 检查在 validateObject 中处理
  }

  // $ref 引用：先解析再递归校验（悬空引用跳过该字段，不阻断）
  if (schema.$ref) {
    const resolved = resolveRef(schema.$ref, root)
    if (!resolved) return
    validateValue(value, resolved, path, errors, root)
    return
  }

  const type = schema.type
  if (!type) return

  if (type === 'string') {
    if (typeof value !== 'string') {
      errors.push(fail(path, `「${path}」必须为文本`, 'type_error.string', value))
      return
    }
    if (schema.minLength !== undefined && value.length < schema.minLength) {
      errors.push(
        fail(
          path,
          `「${path}」长度不能少于 ${schema.minLength} 个字符（当前 ${value.length}）`,
          'min_length',
          value,
        ),
      )
    }
    if (schema.maxLength !== undefined && value.length > schema.maxLength) {
      errors.push(
        fail(
          path,
          `「${path}」长度不能超过 ${schema.maxLength} 个字符（当前 ${value.length}）`,
          'max_length',
          value,
        ),
      )
    }
    if (schema.pattern && !new RegExp(schema.pattern).test(value)) {
      errors.push(fail(path, `「${path}」格式不正确`, 'pattern', value))
    }
    if (schema.format === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      errors.push(fail(path, '邮箱地址格式不正确', 'format.email', value))
    }
  }

  if (type === 'number' || type === 'integer') {
    if (typeof value !== 'number' || Number.isNaN(value)) {
      errors.push(fail(path, `「${path}」必须为数字`, 'type_error.number', value))
      return
    }
    if (type === 'integer' && !Number.isInteger(value)) {
      errors.push(fail(path, `「${path}」必须为整数`, 'type_error.integer', value))
    }
    if (schema.minimum !== undefined && value < schema.minimum) {
      errors.push(fail(path, `「${path}」不能小于 ${schema.minimum}`, 'minimum', value))
    }
    if (schema.maximum !== undefined && value > schema.maximum) {
      errors.push(fail(path, `「${path}」不能大于 ${schema.maximum}`, 'maximum', value))
    }
  }

  if (type === 'boolean' && typeof value !== 'boolean') {
    errors.push(fail(path, `「${path}」必须为布尔值`, 'type_error.boolean', value))
  }

  if (type === 'array') {
    if (!Array.isArray(value)) {
      errors.push(fail(path, `「${path}」必须为列表`, 'type_error.array', value))
      return
    }
    if (schema.items) {
      for (let i = 0; i < value.length; i++) {
        const itemPath = `${path}[${i}]`
        if (schema.items.type === 'object' && schema.items.properties) {
          validateObject(value[i], schema.items, itemPath, errors, root)
        } else {
          validateValue(value[i], schema.items, itemPath, errors, root)
        }
      }
    }
  }

  if (type === 'object' && schema.properties) {
    if (typeof value !== 'object' || value === null) {
      errors.push(fail(path, `「${path}」必须为对象`, 'type_error.object', value))
      return
    }
    validateObject(value as Record<string, unknown>, schema, path, errors, root)
  }
}

function validateObject(
  obj: Record<string, unknown> | null | undefined,
  schema: JSONSchemaProperty,
  path: string,
  errors: FieldError[],
  root: JSONSchema,
): void {
  if (!obj) {
    errors.push(fail(path, `「${path}」不能为空`, 'value_error.null', obj))
    return
  }

  const properties = schema.properties ?? {}
  const required = schema.required ?? []

  // 检查必填字段
  for (const key of required) {
    if (obj[key] === undefined || obj[key] === null) {
      const fieldPath = path ? `${path}.${key}` : key
      errors.push(fail(fieldPath, `「${fieldPath}」为必填字段`, 'required'))
    }
  }

  // 校验每个字段
  for (const [key, propSchema] of Object.entries(properties)) {
    if (obj[key] === undefined || obj[key] === null) {
      continue // 已由 required 检查处理
    }
    const fieldPath = path ? `${path}.${key}` : key
    validateValue(obj[key], propSchema, fieldPath, errors, root)
  }
}

// ── 公开 API ──

/**
 * 根据 JSON Schema 校验数据。
 *
 * @param data - 待校验的数据
 * @param schema - JSON Schema 定义
 * @returns ValidationResult — valid + 错误列表
 *
 * @example
 * ```ts
 * import loginRequestSchema from '@/validation/schemas/auth.schema.json'
 *
 * const result = validate({ username: '', password: '123' }, loginRequestSchema.definitions.LoginRequest)
 * if (!result.valid) {
 *   result.errors.forEach(e => console.log(e.field, e.message))
 * }
 * ```
 */
export function validate(
  data: unknown,
  schema: JSONSchema | JSONSchemaProperty,
  root: JSONSchema = schema as JSONSchema,
): ValidationResult {
  const errors: FieldError[] = []

  if (!data || typeof data !== 'object') {
    return { valid: false, errors: [fail('body', '请求数据不能为空', 'value_error.null', data)] }
  }

  // 入口即 $ref：先解析再校验
  if ((schema as JSONSchemaProperty).$ref) {
    const resolved = resolveRef((schema as JSONSchemaProperty).$ref as string, root)
    if (!resolved) return { valid: true, errors }
    return validate(data, resolved, root)
  }

  // 检查 schema 类型
  const resolvedType = schema.type
  if (resolvedType && resolvedType !== 'object') {
    validateValue(data, schema as JSONSchemaProperty, '', errors, root)
    return { valid: errors.length === 0, errors }
  }

  // 对象类型：提取 properties
  const props =
    (schema as JSONSchema).properties ??
    (schema as JSONSchemaProperty).properties ??
    {}
  const req =
    (schema as JSONSchema).required ??
    (schema as JSONSchemaProperty).required ??
    []

  // 构建虚拟 schema 进行校验
  const virtualSchema: JSONSchemaProperty = { type: 'object', properties: props, required: req }
  validateObject(data as Record<string, unknown>, virtualSchema, '', errors, root)

  return { valid: errors.length === 0, errors }
}

/**
 * 校验数据并返回结果，失败时抛出异常。
 *
 * @throws ValidationError — 包含字段错误列表
 */
export function validateOrThrow(data: unknown, schema: JSONSchema | JSONSchemaProperty): void {
  const result = validate(data, schema)
  if (!result.valid) {
    const err = new Error('数据校验失败') as Error & { fields: FieldError[] }
    err.fields = result.errors
    throw err
  }
}

/**
 * 安全校验 — 校验失败时不抛出，仅返回 errors。
 * 用于响应数据校验（不应阻断业务流程）。
 */
export function validateSafe(
  data: unknown,
  schema: JSONSchema | JSONSchemaProperty,
  root: JSONSchema = schema as JSONSchema,
): ValidationResult {
  try {
    return validate(data, schema, root)
  } catch {
    return {
      valid: false,
      errors: [fail('body', '数据格式异常，无法完成校验', 'value_error.parse')],
    }
  }
}
