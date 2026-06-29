<script setup lang="ts">
/**
 * 演化看板页 — CII 时序曲线（技能需求通胀指数）
 * Task 3 增强: 技能趋势时间线、新兴技能卡片、CII仪表盘、技能对比
 */
import { ref, onMounted, computed } from 'vue'
import { use } from 'echarts/core'
import { LineChart, BarChart, GaugeChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import MainLayout from '@/layouts/MainLayout.vue'
import request from '@/api/request'
import { chartColors, tooltipStyle, splitLineStyle, gaugeColor, legendStyle } from '@/utils/chartTheme'

use([CanvasRenderer, LineChart, BarChart, GaugeChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

interface TrendItem {
  skill_name: string
  trend: string
  confidence: number
  points: number[]
  related_positions: string[]
}

const loading = ref(false)
const quarters = ref<string[]>([])
const items = ref<TrendItem[]>([])
const selectedSkill = ref('')

// 技能对比
const compareSkillA = ref('')
const compareSkillB = ref('')

// 演化详情面板
const drawerVisible = ref(false)
const changelogLoading = ref(false)
const changelogData = ref<any[]>([])
const selectedSkillForDetail = ref('')

const trendLabel: Record<string, string> = { rising: '↑ 上升', stable: '→ 平稳', declining: '↓ 下降' }
const trendTagType: Record<string, string> = { rising: 'success', stable: 'info', declining: 'danger' }
const SERIES_COLORS = chartColors().chart

async function fetchTrends() {
  loading.value = true
  try {
    const data = await request.get('/evolution/trends')
    quarters.value = (data as any).quarters ?? []
    items.value = (data as any).items ?? []
  } catch (e) {
    console.error('[Evolution] Failed to fetch trends:', e)
  } finally {
    loading.value = false
  }
}

// Top 10 CII 时序曲线
const chartOption = computed(() => {
  const filtered = selectedSkill.value
    ? items.value.filter(i => i.skill_name === selectedSkill.value)
    : items.value.slice(0, 10)

  return {
    color: SERIES_COLORS,
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        return params.map(p =>
          `${p.marker} ${p.seriesName}: <b>${p.value}</b>`
        ).join('<br/>')
      },
    },
    legend: {
      bottom: 0,
      data: filtered.map(i => i.skill_name),
      textStyle: { fontSize: 13 },
    },
    grid: { left: 50, right: 30, top: 30, bottom: 50 },
    xAxis: {
      type: 'category',
      data: quarters.value,
      boundaryGap: false,
    },
    yAxis: {
      type: 'value',
      name: 'CII',
      min: 60,
      max: 220,
      splitLine: splitLineStyle(),
    },
    series: filtered.map(i => ({
      name: i.skill_name,
      type: 'line',
      data: i.points,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 3 },
      emphasis: { focus: 'series' },
    })),
  }
})

// 新兴技能 (rising + high confidence)
const emergingSkills = computed(() => {
  return items.value
    .filter(i => i.trend === 'rising')
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 6)
})

// CII 仪表盘 (取全部 rising 技能的平均 CII)
const ciiGaugeOption = computed(() => {
  if (!items.value.length) return {}
  const latestValues = items.value.map(i => i.points?.[i.points.length - 1] ?? 100)
  const avgCii = latestValues.reduce((s, v) => s + v, 0) / latestValues.length
  return {
    series: [{
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 60,
      max: 200,
      progress: { show: true, width: 18, itemStyle: { color: gaugeColor(avgCii) } },
      axisLine: { lineStyle: { width: 18, color: [[0.3, chartColors().success], [0.7, chartColors().warning], [1, chartColors().danger]] } },
      axisTick: { show: false },
      splitLine: { length: 10, lineStyle: { width: 2, color: chartColors().muted } },
      axisLabel: { distance: 25, color: chartColors().muted, fontSize: 11 },
      pointer: { itemStyle: { color: 'auto' } },
      title: { show: true, offsetCenter: [0, '70%'], fontSize: 14, color: chartColors().muted },
      detail: { valueAnimation: true, formatter: '{value}', fontSize: 28, offsetCenter: [0, '40%'], color: 'inherit' },
      data: [{ value: Math.round(avgCii * 10) / 10, name: '平均 CII 指数' }],
    }],
  }
})

// 技能对比图
const compareOption = computed(() => {
  if (!compareSkillA.value || !compareSkillB.value) return null
  const itemA = items.value.find(i => i.skill_name === compareSkillA.value)
  const itemB = items.value.find(i => i.skill_name === compareSkillB.value)
  if (!itemA || !itemB) return null
  return {
    tooltip: { ...tooltipStyle(), trigger: 'axis' },
    legend: { data: [compareSkillA.value, compareSkillB.value], bottom: 0, textStyle: legendStyle() },
    grid: { left: 50, right: 30, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: quarters.value, boundaryGap: false },
    yAxis: { type: 'value', name: 'CII', splitLine: splitLineStyle() },
    series: [
      { name: compareSkillA.value, type: 'line', data: itemA.points, smooth: true, lineStyle: { width: 3, color: chartColors().primary }, itemStyle: { color: chartColors().primary } },
      { name: compareSkillB.value, type: 'line', data: itemB.points, smooth: true, lineStyle: { width: 3, color: chartColors().danger }, itemStyle: { color: chartColors().danger } },
    ],
  }
})

async function fetchChangelog(skillName: string) {
  selectedSkillForDetail.value = skillName
  drawerVisible.value = true
  changelogLoading.value = true
  try {
    const data = await request.get(`/evolution/changelog/${encodeURIComponent(skillName)}`)
    changelogData.value = Array.isArray(data) ? data : ((data as any).changelog ?? (data as any).items ?? [])
  } catch (e) {
    console.error('[Evolution] Failed to fetch changelog:', e)
    changelogData.value = []
  } finally {
    changelogLoading.value = false
  }
}

onMounted(fetchTrends)
</script>

<template>
  <MainLayout>
    <div class="evolution-page animate-fade-in">
      <!-- 标题 -->
      <div class="page-header">
        <div>
          <h2 class="page-title">
            演化趋势看板
          </h2>
          <p class="page-subtitle">
            CII 时序曲线 — 技能需求通胀指数（基准 100 = 2024-Q1）
          </p>
        </div>
        <el-select
          v-model="selectedSkill"
          placeholder="全部技能"
          clearable
          size="small"
          class="select-sm"
        >
          <el-option
            v-for="item in items"
            :key="item.skill_name"
            :label="item.skill_name"
            :value="item.skill_name"
          />
        </el-select>
      </div>

      <!-- KPI 区域: CII 仪表盘 + 新兴技能卡片 -->
      <div class="kpi-row">
        <!-- CII 仪表盘 -->
        <el-card
          class="gauge-card"
          shadow="hover"
        >
          <template #header>
            <div class="card-header-row">
              <span>CII 仪表盘</span><span class="card-header-badge">实时</span>
            </div>
          </template>
          <VChart
            v-if="items.length"
            :option="ciiGaugeOption"
            autoresize
            class="chart-h-gauge"
          />
          <div
            v-else
            class="custom-empty"
          >
            <div class="empty-icon-wrapper">
              <svg
                width="48"
                height="48"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.2"
                stroke-linecap="round"
                stroke-linejoin="round"
              ><path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-3 3" /></svg>
            </div><p class="empty-text">
              图表数据为空
            </p><p class="empty-hint-text">
              技能 CII 数据将在分析完成后展示
            </p>
          </div>
        </el-card>

        <!-- 新兴技能卡片 -->
        <el-card
          class="emerging-card"
          shadow="hover"
        >
          <template #header>
            <div class="card-header-row">
              <span>新兴技能</span><el-tag
                type="success"
                size="small"
                effect="plain"
                class="ml-2"
              >
                rising
              </el-tag>
            </div>
          </template>
          <div class="emerging-grid">
            <div
              v-for="skill in emergingSkills"
              :key="skill.skill_name"
              class="emerging-item"
              @click="fetchChangelog(skill.skill_name)"
            >
              <div class="emerging-name">
                {{ skill.skill_name }}
              </div>
              <div class="emerging-meta">
                <span class="emerging-cii">CII {{ skill.points?.[skill.points.length - 1] ?? '-' }}</span>
                <el-tag
                  size="small"
                  type="success"
                  effect="plain"
                  class="pulse-tag"
                >
                  ↑ {{ ((skill.confidence ?? 0) * 100).toFixed(0) }}%
                </el-tag>
              </div>
            </div>
            <div
              v-if="!emergingSkills.length"
              class="custom-empty"
            >
              <div class="empty-icon-wrapper">
                <svg
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                ><path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-3 3" /></svg>
              </div><p class="empty-text">
                暂未检测到新兴技能
              </p><p class="empty-hint-text">
                当技能 CII 指数出现显著上升时会在此显示
              </p>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 曲线图 -->
      <el-card
        v-loading="loading"
        class="chart-card"
      >
        <template #header>
          CII 时序趋势
        </template>
        <VChart
          v-if="items.length"
          :option="chartOption"
          autoresize
          class="chart-h-lg"
        />
        <div
          v-else
          class="custom-empty"
        >
          <div class="empty-icon-wrapper">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.2"
              stroke-linecap="round"
              stroke-linejoin="round"
            ><ellipse
              cx="12"
              cy="5"
              rx="9"
              ry="3"
            /><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" /><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" /></svg>
          </div><p class="empty-text">
            演化数据待生成
          </p><p class="empty-hint-text">
            CII 时序分析运行后将自动填充
          </p>
        </div>
      </el-card>

      <!-- Task 3: 技能对比 -->
      <el-card
        class="compare-card"
        shadow="hover"
      >
        <template #header>
          技能对比
        </template>
        <div class="compare-selectors">
          <el-select
            v-model="compareSkillA"
            placeholder="选择技能 A"
            clearable
            size="small"
            class="select-md"
          >
            <el-option
              v-for="item in items"
              :key="'A_' + item.skill_name"
              :label="item.skill_name"
              :value="item.skill_name"
            />
          </el-select>
          <span class="compare-vs">VS</span>
          <el-select
            v-model="compareSkillB"
            placeholder="选择技能 B"
            clearable
            size="small"
            class="select-md"
          >
            <el-option
              v-for="item in items"
              :key="'B_' + item.skill_name"
              :label="item.skill_name"
              :value="item.skill_name"
            />
          </el-select>
        </div>
        <VChart
          v-if="compareOption"
          :option="compareOption"
          autoresize
          class="chart-h-md mt-3"
        />
        <div
          v-else
          class="compare-placeholder"
        >
          选择两个技能进行对比分析
        </div>
      </el-card>

      <!-- 趋势概览表 -->
      <el-card class="table-card">
        <template #header>
          趋势概览
        </template>
        <el-table
          :data="items"
          size="small"
          stripe
          @row-click="(row: any) => fetchChangelog(row.skill_name)"
        >
          <el-table-column
            prop="skill_name"
            label="技能"
            min-width="120"
          >
            <template #default="{ row }">
              <el-link type="primary">
                {{ row.skill_name }}
              </el-link>
            </template>
          </el-table-column>
          <el-table-column
            label="趋势"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="trendTagType[row.trend]"
                size="small"
                effect="plain"
              >
                {{ trendLabel[row.trend] ?? row.trend }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="当前 CII"
            width="100"
          >
            <template #default="{ row }">
              <b>{{ row.points?.[row.points.length - 1] ?? '-' }}</b>
            </template>
          </el-table-column>
          <el-table-column
            label="变化"
            width="100"
          >
            <template #default="{ row }">
              <span
                v-if="row.points?.length"
                :class="row.points.at(-1)! >= 100 ? 'cii-up' : 'cii-down'"
              >
                {{ row.points.at(-1)! >= 100 ? '+' : '' }}{{ row.points.at(-1)! - 100 }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column
            label="置信度"
            width="90"
          >
            <template #default="{ row }">
              {{ ((row.confidence ?? 0) * 100).toFixed(0) }}%
            </template>
          </el-table-column>
          <el-table-column
            label="关联岗位"
            min-width="200"
          >
            <template #default="{ row }">
              <el-tag
                v-for="pos in row.related_positions"
                :key="pos"
                size="small"
                class="related-tag"
              >
                {{ pos }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 演化详情抽屉 -->
      <el-drawer
        v-model="drawerVisible"
        :title="`${selectedSkillForDetail} 演化历史`"
        size="400px"
      >
        <div v-loading="changelogLoading">
          <el-timeline v-if="changelogData.length">
            <el-timeline-item
              v-for="(item, idx) in changelogData"
              :key="idx"
              :timestamp="item.date ?? item.created_at ?? ''"
              placement="top"
            >
              <el-card shadow="never">
                <p><b>{{ item.change_type ?? '变更' }}</b>: {{ item.description ?? item.detail ?? '' }}</p>
                <p
                  v-if="item.trust_score"
                  class="trust-meta"
                >
                  信任度: {{ (item.trust_score * 100).toFixed(0) }}%
                </p>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <div
            v-else
            class="custom-empty"
          >
            <div class="empty-icon-wrapper">
              <svg
                width="48"
                height="48"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.2"
                stroke-linecap="round"
                stroke-linejoin="round"
              ><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line
                x1="16"
                y1="13"
                x2="8"
                y2="13"
              /><line
                x1="16"
                y1="17"
                x2="8"
                y2="17"
              /><polyline points="10 9 9 9 8 9" /></svg>
            </div><p class="empty-text">
              该技能暂无变更记录
            </p>
          </div>
        </div>
      </el-drawer>
    </div>
  </MainLayout>
</template>

<style scoped>
.evolution-page {
  min-height: 400px;
}
.page-title {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}
.page-subtitle {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-6);
}
.page-header h2 {
  margin: 0 0 4px;
  font-size: var(--font-size-3xl);
  color: var(--foreground);
  font-weight: 800;
  letter-spacing: var(--tracking-tight);
}
.subtitle {
  margin: 0;
  font-size: var(--font-size-base);
  color: var(--muted-foreground);
}

/* KPI 行 */
.kpi-row {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.gauge-card {
  flex: 0 0 320px;
}
.emerging-card {
  flex: 1;
  min-width: 0;
}
.emerging-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--space-3);
}
.emerging-item {
  padding: var(--space-3) var(--space-4);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}
.emerging-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--success);
  border-radius: 0 2px 2px 0;
  opacity: 0;
  transition: opacity var(--duration-fast);
}
.emerging-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: color-mix(in srgb, var(--success) 40%, var(--border));
}
.emerging-item:hover::before { opacity: 1; }
.emerging-name {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin-bottom: var(--space-1);
  letter-spacing: var(--tracking-tight);
}
.emerging-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.emerging-cii {
  font-size: var(--font-size-xs);
  color: var(--success);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.pulse-tag {
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
.chart-card {
  margin-bottom: var(--space-5);
}
.compare-card {
  margin-bottom: var(--space-5);
}
.compare-selectors {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.compare-vs {
  font-size: var(--font-size-lg);
  font-weight: 800;
  color: var(--muted-foreground);
  letter-spacing: var(--tracking-tight);
}
.compare-placeholder {
  text-align: center;
  padding: var(--space-10);
  color: var(--muted-foreground);
  font-size: var(--font-size-base);
}
.table-card {
  margin-bottom: var(--space-5);
}
.related-tag {
  margin-right: var(--space-2);
  margin-bottom: var(--space-1);
}
@media (max-width: 768px) {
  .kpi-row { flex-direction: column; }
  .gauge-card { flex: 1; }
  .compare-selectors { flex-direction: column; align-items: stretch; }
}
.cii-up { color: var(--success); font-weight: 600; font-variant-numeric: tabular-nums; }
.cii-down { color: var(--destructive); font-weight: 600; font-variant-numeric: tabular-nums; }
.trust-meta { color: var(--muted-foreground); font-size: var(--font-size-xs); }
.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.card-header-badge {
  font-size: 10px;
  font-weight: 600;
  color: var(--success);
  background: var(--success-ghost);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  letter-spacing: 0.04em;
}
.select-sm { width: 160px; }
.select-md { width: 180px; }
.chart-h-gauge { height: 240px; }
.chart-h-lg { height: 420px; }
.chart-h-md { height: 300px; }
.ml-2 { margin-left: var(--space-2); }
.mt-3 { margin-top: var(--space-3); }

/* ── Custom Empty State ── */
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) var(--space-6);
  text-align: center;
}
.empty-icon-wrapper {
  color: var(--muted-foreground);
  opacity: 0.4;
  margin-bottom: var(--space-4);
}
.empty-text {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}
.empty-hint-text {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}
.empty-slot {
  margin-top: var(--space-4);
}
</style>