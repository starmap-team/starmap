/**
 * Element Plus type helpers — narrow runtime strings to el-tag's literal union.
 * el-tag :type expects '' | 'success' | 'warning' | 'danger' | 'info',
 * but computed values resolve to `string` and TS rejects the assignment.
 */

export type ElTagType = '' | 'success' | 'warning' | 'danger' | 'info'

const VALID_TAG_TYPES: readonly string[] = ['', 'success', 'warning', 'danger', 'info']

/** Narrow a runtime string to ElTagType, falling back to `'info'` (or a custom fallback). */
export function asTagType(value: string | undefined, fallback: ElTagType = 'info'): ElTagType {
  return value && VALID_TAG_TYPES.includes(value) ? value as ElTagType : fallback
}
