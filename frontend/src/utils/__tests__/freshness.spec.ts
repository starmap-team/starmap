/**
 * freshness.ts — 数据时效指示工具测试
 *
 * 覆盖 4 档：无时间戳/非法时间戳 = 演示数据；≤7 天 = 数据更新于；
 * ≤30 天 = 数据更新于 (N天前)；>30 天 = 数据较旧。
 */
import { describe, it, expect } from 'vitest'
import { freshnessOf } from '../freshness'

describe('freshnessOf', () => {
  it('returns demo-data badge when discovered_at is null/undefined', () => {
    expect(freshnessOf(null)).toEqual({ label: '演示数据', type: 'info' })
    expect(freshnessOf(undefined)).toEqual({ label: '演示数据', type: 'info' })
  })

  it('returns demo-data badge for invalid timestamps (honesty: no fabrication)', () => {
    expect(freshnessOf('not-a-date')).toEqual({ label: '演示数据', type: 'info' })
  })

  it('returns success badge when updated within 7 days', () => {
    const recent = new Date(Date.now() - 3 * 86400000).toISOString()
    const info = freshnessOf(recent)
    expect(info.type).toBe('success')
    expect(info.label).toContain('数据更新于')
  })

  it('returns warning badge when updated 8-30 days ago', () => {
    const old = new Date(Date.now() - 20 * 86400000).toISOString()
    const info = freshnessOf(old)
    expect(info.type).toBe('warning')
    expect(info.label).toContain('20天前')
  })

  it('returns danger badge when updated over 30 days ago', () => {
    const stale = new Date(Date.now() - 90 * 86400000).toISOString()
    const info = freshnessOf(stale)
    expect(info.type).toBe('danger')
    expect(info.label).toContain('数据较旧')
  })
})
