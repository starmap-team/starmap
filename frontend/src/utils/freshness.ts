/**
 * 数据时效指示（PLAN-006④）。
 *
 * 由岗位/技能入库时间 discovered_at 推导 3 档友好标签 + tag 类型。
 * 无时间戳或时间戳非法 = "演示数据"（诚实标注：未采集，不得编造时间）。
 */
export interface FreshnessInfo {
  label: string
 /** Element Plus el-tag type */
  type: string
}

export function freshnessOf(discoveredAt: string | null | undefined): FreshnessInfo {
  if (!discoveredAt) return { label: '演示数据', type: 'info' }
  const ts = Date.parse(discoveredAt)
  if (Number.isNaN(ts)) return { label: '演示数据', type: 'info' }
  const days = Math.floor((Date.now() - ts) / 86400000)
  const date = new Date(ts).toISOString().slice(0, 10)
  if (days <= 7) return { label: `数据更新于 ${date}`, type: 'success' }
  if (days <= 30) return { label: `数据更新于 ${date} (${days}天前)`, type: 'warning' }
  return { label: `数据较旧 (${date}, ${days}天前)`, type: 'danger' }
}
