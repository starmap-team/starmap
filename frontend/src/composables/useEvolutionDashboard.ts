/**
 * Unified EvolutionDashboard composable — merges 3 single-caller composables:
 * useEvolutionFormatters (27L) + useEvolutionActions (82L) + useEvolutionCharts (122L)
 * All 3 served only by EvolutionDashboard.vue.
 */
import { computed, ref, type Ref, type ComputedRef } from 'vue'
import { ElMessage } from 'element-plus'
import { chartColors, tooltipStyle, splitLineStyle, gaugeColor, legendStyle } from '@/utils/chartTheme'
import type { useEvolutionStore, SnapshotEntry, TrendItem } from '@/stores/evolution'

type EvolutionStore = ReturnType<typeof useEvolutionStore>

// ===== Formatters =====

export function formatChange(points: number[] | undefined): string {
  if (!points?.length) return '-'
  const last = points[points.length - 1] ?? 0
  const delta = last - 100
  const sign = delta >= 0 ? '+' : ''
  return sign + delta.toFixed(1) + '%'
}

export const TREND_LABEL: Record<string, string> = {
  rising: '↑ 上升', emerging: '★ 涌现', stable: '→ 平稳', declining: '↓ 下降',
}

export const TREND_TAG_TYPE: Record<string, string> = {
  rising: 'success', emerging: 'warning', stable: 'info', declining: 'danger',
}

// ===== Actions / Drawer =====

export interface EvolutionActionsApi {
  drawerVisible: Ref<boolean>
  evidenceDrawerOpen: Ref<boolean>
  selectedSkillForDetail: Ref<string>
  snapshotIndex: Ref<number>
  selectedSnapshotDate: Ref<string>
  fetchTrends: () => Promise<void>
  fetchSnapshots: () => Promise<void>
  fetchChangelog: (identifier: string) => Promise<void>
  onSnapshotChange: (idx: number | number[]) => void
  refresh: () => Promise<void>
}

export function useEvolutionActions(store: EvolutionStore): EvolutionActionsApi {
  const drawerVisible = ref(false)
  const evidenceDrawerOpen = ref(false) // D-09: 证据区默认折叠不打扰
  const selectedSkillForDetail = ref('')
  const snapshotIndex = ref(0)
  const selectedSnapshotDate = ref('')

  async function fetchTrends(): Promise<void> {
    try { await store.fetchTrends() } catch (e) {
      if (import.meta.env.DEV) console.error('[Evolution] Failed to fetch trends:', e)
      ElMessage.error('演化趋势数据加载失败')
    }
  }

  async function fetchSnapshots(): Promise<void> {
    try {
      await store.fetchSnapshots()
      const last = store.snapshots.length - 1
      if (last >= 0) { snapshotIndex.value = last; const s: SnapshotEntry | undefined = store.snapshots[last]; if (s) selectedSnapshotDate.value = s.snapshot_date }
    } catch (e) { if (import.meta.env.DEV) console.error('[Evolution] Failed to fetch snapshots:', e) }
  }

  function onSnapshotChange(idx: number | number[]): void {
    const i = Array.isArray(idx) ? idx[0] : idx
    const snap: SnapshotEntry | undefined = store.snapshots[i ?? 0]
    if (snap) {
      selectedSnapshotDate.value = snap.snapshot_date
 // E1: 快照时间线联动次区 —— 拉取该岗位真实 CII 历史（非装饰滑块）
      void store.fetchCiiHistory(snap.position_name)
      ElMessage.info(`已切换到快照 ${snap.snapshot_date}（${snap.position_name}）`)
    }
  }

  async function fetchChangelog(identifier: string): Promise<void> {
    selectedSkillForDetail.value = identifier; drawerVisible.value = true
    try { await store.fetchChangelog(identifier) } catch (e) {
      if (import.meta.env.DEV) console.error('[Evolution] Failed to fetch changelog:', e)
    }
  }

 // 10-03 : 手动刷新 — 复用同一 fetch 集合，并发触发
  async function refresh(): Promise<void> {
    try {
      await store.refreshAll()
    } catch (e) {
      if (import.meta.env.DEV) console.error('[Evolution] Refresh failed:', e)
      ElMessage.error('演化数据刷新失败')
    }
  }

  return { drawerVisible, evidenceDrawerOpen, selectedSkillForDetail, snapshotIndex, selectedSnapshotDate, fetchTrends, fetchSnapshots, fetchChangelog, onSnapshotChange, refresh }
}

// ===== Charts =====

export function useEvolutionCharts(
  items: ComputedRef<TrendItem[]>, selectedSkill: Ref<string>,
  compareSkillA: Ref<string>, compareSkillB: Ref<string>,
) {
  const cc = chartColors()

  const chartOption = computed(() => {
    if (!items.value.length) return {}
 // E7: 全量技能（不再截断 [:20]）后，306 项单折线不可读 → 改为 CII 当前值分布直方图，
 // 任意技能规模均可读；逐技能明细见下方「趋势概览」表，逐技能时序见「技能对比」。
    const BUCKETS = [
      { label: '<60', min: -Infinity, max: 60 },
      { label: '60-80', min: 60, max: 80 },
      { label: '80-100', min: 80, max: 100 },
      { label: '100-120', min: 100, max: 120 },
      { label: '120-140', min: 120, max: 140 },
      { label: '>140', min: 140, max: Infinity },
    ]
    const counts = BUCKETS.map(b => ({ label: b.label, count: 0 }))
    for (const i of items.value) {
      const last = i.points?.length ? i.points[i.points.length - 1] : 100
      const idx = BUCKETS.findIndex(b => last >= b.min && last < b.max)
      counts[idx === -1 ? 0 : idx].count += 1
    }
    return {
      tooltip: tooltipStyle(), legend: legendStyle(),
      xAxis: { type: 'category', data: counts.map(c => c.label), axisLabel: { color: cc.muted, fontSize: 10 }, splitLine: splitLineStyle() },
      yAxis: { type: 'value', axisLabel: { color: cc.muted }, name: '技能数' },
      series: [{ type: 'bar', data: counts.map(c => c.count), barWidth: '55%', itemStyle: { color: cc.chart[0], borderRadius: [4, 4, 0, 0] }, label: { show: true, position: 'top', color: cc.muted, fontSize: 11 } }],
    }
  })

  const ciiGaugeOption = computed(() => {
    if (!items.value.length) return {}
 // E3: 「全部技能」模式下不渲染空白仪表盘 —— 改为全技能末点均值（与 KPI cii_mean 同口径）
    const sel = selectedSkill.value ? items.value.find(i => i.skill_name === selectedSkill.value) : undefined
    const points = sel?.points?.length
      ? sel.points
      : items.value.flatMap(i => (i.points?.length ? [i.points[i.points.length - 1]] : []))
    const lastPoint = points.length
      ? (points.reduce((a, b) => a + b, 0) / points.length)
      : 100
    const name = sel?.skill_name ?? `全部技能均值（${items.value.length} 项）`
    return {
      series: [{
        type: 'gauge', min: 60, max: 140, radius: '95%', center: ['50%', '58%'],
        detail: { formatter: '{value}%', color: cc.foreground, fontSize: 24, offsetCenter: [0, '70%'] },
        title: { fontSize: 13, color: cc.muted, offsetCenter: [0, '105%'] },
        axisLine: { lineStyle: { color: [[0.3, cc.success], [0.7, cc.warning], [1, cc.danger]], width: 16 } },
        data: [{ value: Math.round(lastPoint * 10) / 10, name }], itemStyle: { color: gaugeColor(lastPoint) },
      }],
    }
  })

  const compareOption = computed(() => {
    if (!compareSkillA.value || !compareSkillB.value) return {}
    const a = items.value.find(i => i.skill_name === compareSkillA.value)
    const b = items.value.find(i => i.skill_name === compareSkillB.value)
    if (!a?.points?.length || !b?.points?.length) return {}
    return {
      tooltip: tooltipStyle(), legend: legendStyle(),
      xAxis: { type: 'category', data: a.points.map((_, i) => `T${i + 1}`), axisLabel: { color: cc.muted, fontSize: 10 } },
      yAxis: { type: 'value', axisLabel: { color: cc.muted } },
      series: [
        { name: compareSkillA.value, type: 'line', data: a.points, smooth: true, itemStyle: { color: cc.chart[0] } },
        { name: compareSkillB.value, type: 'line', data: b.points, smooth: true, itemStyle: { color: cc.chart[2] } },
      ],
    }
  })

 // C1: 新兴技能卡片的渲染数据源是 items 的 rising/emerging 子集（在页面 computed 中过滤），
 // 不再在此暴露 ECharts option —— 避免被模板当技能列表迭代（误渲染 garbage cards）。
  return { chartOption, ciiGaugeOption, compareOption }
}
