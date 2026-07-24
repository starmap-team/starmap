/**
 * 表单预提交校验 Composable。
 *
 * 在表单提交前基于 JSON Schema 进行本地校验，
 * 提供即时反馈，避免无效请求发送到后端。
 *
 * 支持：
 * - Element Plus Form 集成（el-form ref 的 validateField）
 * - 独立校验（不依赖 UI 库）
 * - 嵌套表单字段路径映射
 *
 * @example
 * ```vue
 * <script setup lang="ts">
 * import { useFormValidation } from '@/validation/useFormValidation'
 * import loginSchema from '@/validation/schemas/auth.schema.json'
 *
 * const { validate, errors, fieldErrors, reset } = useFormValidation(
 *   loginSchema.definitions.LoginRequest
 * )
 *
 * async function handleSubmit() {
 *   const formData = { username: form.username, password: form.password }
 *   if (!validate(formData)) return
 *   // 校验通过，发送请求...
 * }
 * </script>
 * ```
 */

import { computed, ref, type Ref } from 'vue'
import { validate as validateSchema } from './validate'
import type { FieldError, JSONSchema, JSONSchemaProperty } from './types'

export interface UseFormValidationOptions {
  /** 表单标签映射（用于错误消息中将字段名替换为中文标签） */
  labels?: Record<string, string>
  /** 是否在首次校验前跳过（用于初始加载场景） */
  lazy?: boolean
}

export interface UseFormValidationReturn {
  /** 执行全量校验，返回是否通过 */
  validate: (data: Record<string, unknown>) => boolean
  /** 校验单个字段 */
  validateField: (field: string, value: unknown) => string | null
  /** 校验错误列表 */
  errors: Ref<FieldError[]>
  /** 字段 → 错误消息映射（可直接绑定到 el-form-item error prop） */
  fieldErrors: Ref<Record<string, string>>
  /** 是否存在校验错误 */
  hasErrors: Ref<boolean>
  /** 重置所有错误状态 */
  reset: () => void
}

/**
 * 创建表单校验实例。
 *
 * @param schema - JSON Schema 定义（schema.definitions.XXX 或直接 schema）
 * @param options - 配置选项
 */
export function useFormValidation(
  schema: JSONSchema | JSONSchemaProperty,
  options: UseFormValidationOptions = {},
): UseFormValidationReturn {
  const errors = ref<FieldError[]>([])
  const labels = options.labels ?? {}

  const fieldErrors = computed(() => {
    const map: Record<string, string> = {}
    for (const err of errors.value) {
      const label = labels[err.field] ?? err.field
      map[err.field] = `${label}：${err.message}`
    }
    return map
  })

  const hasErrors = computed(() => errors.value.length > 0)

  function validate(data: Record<string, unknown>): boolean {
    const result = validateSchema(data, schema)
    errors.value = result.errors.map((e) => ({
      ...e,
      message: formatFieldMessage(e, labels),
    }))
    return result.valid
  }

  function validateField(field: string, value: unknown): string | null {
    // 构建单字段临时 schema
    const props = (schema as JSONSchema).properties ?? (schema as JSONSchemaProperty).properties ?? {}
    const fieldSchema = props[field]
    if (!fieldSchema) return null

    // 简单检查：是否为必填且为空
    const required = (schema as JSONSchema).required ?? (schema as JSONSchemaProperty).required ?? []
    if (required.includes(field) && (value === undefined || value === null || value === '')) {
      return `「${labels[field] ?? field}」为必填字段`
    }

    // 更多约束由 validateSchema 处理
    // 这里做轻量检查避免为每个字段执行完整校验
    if (fieldSchema.type === 'string' && typeof value === 'string') {
      if (fieldSchema.minLength && value.length < fieldSchema.minLength) {
        return `长度不能少于 ${fieldSchema.minLength} 个字符`
      }
      if (fieldSchema.maxLength && value.length > fieldSchema.maxLength) {
        return `长度不能超过 ${fieldSchema.maxLength} 个字符`
      }
      if (fieldSchema.pattern && !new RegExp(fieldSchema.pattern).test(value)) {
        return '格式不正确'
      }
    }
    if (
      (fieldSchema.type === 'number' || fieldSchema.type === 'integer') &&
      typeof value === 'number'
    ) {
      if (fieldSchema.minimum !== undefined && value < fieldSchema.minimum) {
        return `不能小于 ${fieldSchema.minimum}`
      }
      if (fieldSchema.maximum !== undefined && value > fieldSchema.maximum) {
        return `不能大于 ${fieldSchema.maximum}`
      }
    }

    return null
  }

  function reset(): void {
    errors.value = []
  }

  return {
    validate,
    validateField,
    errors,
    fieldErrors,
    hasErrors,
    reset,
  }
}

/** 将字段路径替换为中文标签 */
function formatFieldMessage(
  err: FieldError,
  labels: Record<string, string>,
): string {
  // 尝试完整路径映射
  if (labels[err.field]) {
    return err.message.replace(err.field, labels[err.field])
  }
  // 尝试逐段替换
  const parts = err.field.split('.')
  const translated = parts.map((p) => labels[p] ?? p).join('.')
  return err.message.replace(err.field, translated)
}
