/**
 * Unified EvolutionDashboard composable — merges 3 single-caller composables:
 *   useEvolutionFormatters (27L) + useEvolutionActions (82L) + useEvolutionCharts (122L)
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
  selectedSkillForDetail: Ref<string>
  snapshotIndex: Ref<number>
  selectedSnapshotDate: Ref<string>
  fetchTrends: () => Promise<void>
  fetchSnapshots: () => Promise<void>
  fetchChangelog: (identifier: string) => Promise<void>
  onSnapshotChange: (idx: number | number[]) => void
}

export function useEvolutionActions(store: EvolutionStore): EvolutionActionsApi {
  const drawerVisible = ref(false)
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
    if (snap) { selectedSnapshotDate.value = snap.snapshot_date; ElMessage.info(`已切换到快照 ${snap.snapshot_date}（${snap.position_name}）`) }
  }

  async function fetchChangelog(identifier: string): Promise<void> {
    selectedSkillForDetail.value = identifier; drawerVisible.value = true
    try { await store.fetchChangelog(identifier) } catch (e) {
      if (import.meta.env.DEV) console.error('[Evolution] Failed to fetch changelog:', e)
    }
  }

  return { drawerVisible, selectedSkillForDetail, snapshotIndex, selectedSnapshotDate, fetchTrends, fetchSnapshots, fetchChangelog, onSnapshotChange }
}

// ===== Charts =====

export function useEvolutionCharts(
  items: ComputedRef<TrendItem[]>, selectedSkill: Ref<string>,
  compareSkillA: Ref<string>, compareSkillB: Ref<string>,
) {
  const cc = chartColors()

  const chartOption = computed(() => {
    if (!items.value.length) return {}
    const dates = items.value.map(i => i.skill_name)
    const cii = items.value.map(i => i.points?.length ? i.points[i.points.length - 1] : 100)
    return {
      tooltip: tooltipStyle(), legend: legendStyle(),
      xAxis: { type: 'category', data: dates, axisLabel: { color: cc.muted, fontSize: 10 }, splitLine: splitLineStyle() },
      yAxis: { type: 'value', axisLabel: { color: cc.muted } },
      series: [{ type: 'line', data: cii, smooth: true, itemStyle: { color: cc.chart[0] }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: cc.chart[0] + '33' }, { offset: 1, color: cc.chart[0] + '00' }] } } }],
    }
  })

  const emergingSkills = computed(() => {
    if (!items.value.length) return {}
    const rising = items.value.filter(i => i.trend === 'rising' || i.trend === 'emerging')
    if (!rising.length) return {}
    return {
      tooltip: tooltipStyle(),
      xAxis: { type: 'value', axisLabel: { color: cc.muted } },
      yAxis: { type: 'category', data: rising.map(i => i.skill_name), axisLabel: { color: cc.muted } },
      series: [{ type: 'bar', data: rising.map(i => i.confidence * 100), itemStyle: { color: cc.chart[1] } }],
      grid: { left: 80 },
    }
  })

  const ciiGaugeOption = computed(() => {
    const sel = items.value.find(i => i.skill_name === selectedSkill.value)
    if (!sel) return {}
    const lastPoint = sel.points?.length ? sel.points[sel.points.length - 1] : 100
    return {
      series: [{ type: 'gauge', min: 60, max: 140, detail: { formatter: '{value}%', color: cc.foreground, fontSize: 18 }, axisLine: { lineStyle: { color: [[0.3, cc.success], [0.7, cc.warning], [1, cc.danger]], width: 12 } }, data: [{ value: lastPoint, name: 'CII' }], itemStyle: { color: gaugeColor(lastPoint) } }],
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

  return { chartOption, emergingSkills, ciiGaugeOption, compareOption }
}
