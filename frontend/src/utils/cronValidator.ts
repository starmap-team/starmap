// Cron 表达式完整校验工具 ( Plan 03 Task 11).
//
// 5 字段值域 + 范围校验：
// - 分 (minute): 0-59
// - 时 (hour): 0-23
// - 日 (day of month): 1-31
// - 月 (month): 1-12
// - 周 (day of week): 0-6 (周日=0 或 7)
//
// 支持：
// - 通配符 star
// - 步长 slash (例如 star-slash-N 或 a-b-slash-N)
// - 列表 (例如 1,2,3)
// - 范围 a-b
// - 单值 N

export interface CronValidationError {
  field: 'minute' | 'hour' | 'day' | 'month' | 'week'
  value: string
  message: string
}

export interface CronValidationResult {
  valid: boolean
  errors: CronValidationError[]
 /** 5 字段解析结果（trim 后） */
  parsed?: {
    minute: string
    hour: string
    day: string
    month: string
    week: string
  }
}

const FIELD_BOUNDS = {
  minute: { min: 0, max: 59, label: '分' },
  hour: { min: 0, max: 23, label: '时' },
  day: { min: 1, max: 31, label: '日' },
  month: { min: 1, max: 12, label: '月' },
 // 周允许 0-7（0 和 7 都表示周日）
  week: { min: 0, max: 7, label: '周' },
} as const

const FIELD_ORDER: Array<keyof typeof FIELD_BOUNDS> = ['minute', 'hour', 'day', 'month', 'week']

/** 解析单个值（含通配符/范围/列表/步长），返回是否在范围内 */
function validateFieldValue(raw: string, min: number, max: number, field: CronValidationError['field']): CronValidationError[] {
  const errors: CronValidationError[] = []

 // 通配符
  if (raw === '*') return errors

 // 步长：*/N 或 a-b/N
  if (raw.includes('/')) {
    const [range, stepStr] = raw.split('/', 2)
    const step = Number(stepStr)
    if (!Number.isInteger(step) || step < 1 || step > max) {
      errors.push({
        field,
        value: raw,
        message: `${FIELD_BOUNDS[field].label} 步长越界（1-${max}）`,
      })
      return errors
    }
 // range 可以是 * 或 a-b
    if (range !== '*') {
      errors.push(...validateFieldValue(range, min, max, field))
    }
    return errors
  }

 // 列表：a,b,c
  if (raw.includes(',')) {
    for (const part of raw.split(',')) {
      errors.push(...validateFieldValue(part.trim(), min, max, field))
    }
    return errors
  }

 // 范围：a-b
  if (raw.includes('-')) {
    const [startStr, endStr] = raw.split('-', 2)
    const start = Number(startStr)
    const end = Number(endStr)
    if (!Number.isInteger(start) || !Number.isInteger(end)) {
      errors.push({ field, value: raw, message: `${FIELD_BOUNDS[field].label} 范围格式错误` })
      return errors
    }
    if (start < min || start > max) {
      errors.push({ field, value: raw, message: `${FIELD_BOUNDS[field].label} 起始值越界（${min}-${max}）` })
    }
    if (end < min || end > max) {
      errors.push({ field, value: raw, message: `${FIELD_BOUNDS[field].label} 结束值越界（${min}-${max}）` })
    }
    return errors
  }

 // 单值
  const num = Number(raw)
  if (!Number.isInteger(num)) {
    errors.push({ field, value: raw, message: `${FIELD_BOUNDS[field].label} 必须为整数` })
    return errors
  }
  if (num < min || num > max) {
    errors.push({ field, value: raw, message: `${FIELD_BOUNDS[field].label} 越界（${min}-${max}）` })
  }
  return errors
}

/**
 * 完整校验 cron 表达式
 * @param cron 5 字段 cron 表达式（空格分隔）
 */
export function validateCron(cron: string): CronValidationResult {
  if (!cron || !cron.trim()) {
    return { valid: false, errors: [{ field: 'minute', value: '', message: 'Cron 表达式不能为空' }] }
  }
  const parts = cron.trim().split(/\s+/)
  if (parts.length !== 5) {
    return {
      valid: false,
      errors: [{ field: 'minute', value: cron, message: `需要 5 个字段（分 时 日 月 周），当前 ${parts.length} 个` }],
    }
  }
  const errors: CronValidationError[] = []
  for (let i = 0; i < FIELD_ORDER.length; i++) {
    const field = FIELD_ORDER[i]
    const bounds = FIELD_BOUNDS[field]
    errors.push(...validateFieldValue(parts[i], bounds.min, bounds.max, field))
  }
  return {
    valid: errors.length === 0,
    errors,
    parsed: {
      minute: parts[0],
      hour: parts[1],
      day: parts[2],
      month: parts[3],
      week: parts[4],
    },
  }
}

/** 5 字段 cron 常用示例（ tooltip） */
export const CRON_EXAMPLES = [
  { expression: '0 2 * * *', description: '每天凌晨 2 点' },
  { expression: '*/15 * * * *', description: '每 15 分钟' },
  { expression: '0 9-18 * * 1-5', description: '工作日 9-18 点整点' },
  { expression: '0 0 1 * *', description: '每月 1 号 0 点' },
  { expression: '30 4 1,15 * *', description: '每月 1/15 号 4:30' },
]