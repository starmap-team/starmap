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
const SERIES_COLORS = ['#E040FB', '#36CFC9', '#409EFF', '#67C23A', '#F56C6C']

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
      splitLine: { lineStyle: { type: 'dashed', color: '#e8e8e8' } },
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
      progress: { show: true, width: 18, itemStyle: { color: avgCii > 120 ? '#F56C6C' : avgCii > 100 ? '#E6A23C' : '#67C23A' } },
      axisLine: { lineStyle: { width: 18, color: [[0.3, '#67C23A'], [0.7, '#E6A23C'], [1, '#F56C6C']] } },
      axisTick: { show: false },
      splitLine: { length: 10, lineStyle: { width: 2, color: '#999' } },
      axisLabel: { distance: 25, color: '#999', fontSize: 11 },
      pointer: { itemStyle: { color: 'auto' } },
      title: { show: true, offsetCenter: [0, '70%'], fontSize: 14, color: '#606266' },
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
    tooltip: { trigger: 'axis' },
    legend: { data: [compareSkillA.value, compareSkillB.value], bottom: 0 },
    grid: { left: 50, right: 30, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: quarters.value, boundaryGap: false },
    yAxis: { type: 'value', name: 'CII', splitLine: { lineStyle: { type: 'dashed', color: '#e8e8e8' } } },
    series: [
      { name: compareSkillA.value, type: 'line', data: itemA.points, smooth: true, lineStyle: { width: 3, color: '#409EFF' }, itemStyle: { color: '#409EFF' } },
      { name: compareSkillB.value, type: 'line', data: itemB.points, smooth: true, lineStyle: { width: 3, color: '#F56C6C' }, itemStyle: { color: '#F56C6C' } },
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
    <div class="evolution-page">
      <!-- 标题 -->
      <div class="page-header">
        <div>
          <h2>演化趋势看板</h2>
          <p class="subtitle">CII 时序曲线 — 技能需求通胀指数（基准 100 = 2024-Q1）</p>
        </div>
        <el-select v-model="selectedSkill" placeholder="全部技能" clearable size="small" style="width: 160px">
          <el-option v-for="item in items" :key="item.skill_name" :label="item.skill_name" :value="item.skill_name" />
        </el-select>
      </div>

      <!-- KPI 区域: CII 仪表盘 + 新兴技能卡片 -->
      <div class="kpi-row">
        <!-- CII 仪表盘 -->
        <el-card class="gauge-card" shadow="hover">
          <template #header>📊 CII 仪表盘</template>
          <VChart v-if="items.length" :option="ciiGaugeOption" autoresize style="height: 240px" />
          <el-empty v-else description="暂无数据" />
        </el-card>

        <!-- 新兴技能卡片 -->
        <el-card class="emerging-card" shadow="hover">
          <template #header>
            <span>🚀 新兴技能</span>
            <el-tag type="success" size="small" effect="plain" style="margin-left: 8px">rising</el-tag>
          </template>
          <div class="emerging-grid">
            <div v-for="skill in emergingSkills" :key="skill.skill_name" class="emerging-item" @click="fetchChangelog(skill.skill_name)">
              <div class="emerging-name">{{ skill.skill_name }}</div>
              <div class="emerging-meta">
                <span class="emerging-cii">CII {{ skill.points?.[skill.points.length - 1] ?? '-' }}</span>
                <el-tag size="small" type="success" effect="plain" class="pulse-tag">↑ {{ ((skill.confidence ?? 0) * 100).toFixed(0) }}%</el-tag>
              </div>
            </div>
            <el-empty v-if="!emergingSkills.length" description="暂无新兴技能" />
          </div>
        </el-card>
      </div>

      <!-- 曲线图 -->
      <el-card v-loading="loading" class="chart-card">
        <template #header>📈 CII 时序趋势</template>
        <VChart v-if="items.length" :option="chartOption" autoresize style="height: 420px" />
        <el-empty v-else description="暂无演化数据" />
      </el-card>

      <!-- Task 3: 技能对比 -->
      <el-card class="compare-card" shadow="hover">
        <template #header>⚖️ 技能对比</template>
        <div class="compare-selectors">
          <el-select v-model="compareSkillA" placeholder="选择技能 A" clearable size="small" style="width: 180px">
            <el-option v-for="item in items" :key="'A_' + item.skill_name" :label="item.skill_name" :value="item.skill_name" />
          </el-select>
          <span class="compare-vs">VS</span>
          <el-select v-model="compareSkillB" placeholder="选择技能 B" clearable size="small" style="width: 180px">
            <el-option v-for="item in items" :key="'B_' + item.skill_name" :label="item.skill_name" :value="item.skill_name" />
          </el-select>
        </div>
        <VChart v-if="compareOption" :option="compareOption" autoresize style="height: 300px; margin-top: 12px" />
        <div v-else class="compare-placeholder">选择两个技能进行对比分析</div>
      </el-card>

      <!-- 趋势概览表 -->
      <el-card class="table-card">
        <template #header>趋势概览</template>
        <el-table :data="items" size="small" stripe @row-click="(row: any) => fetchChangelog(row.skill_name)">
          <el-table-column prop="skill_name" label="技能" min-width="120">
            <template #default="{ row }">
              <el-link type="primary">{{ row.skill_name }}</el-link>
            </template>
          </el-table-column>
          <el-table-column label="趋势" width="100">
            <template #default="{ row }">
              <el-tag :type="trendTagType[row.trend]" size="small" effect="plain">{{ trendLabel[row.trend] ?? row.trend }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="当前 CII" width="100">
            <template #default="{ row }"><b>{{ row.points?.[row.points.length - 1] ?? '-' }}</b></template>
          </el-table-column>
          <el-table-column label="变化" width="100">
            <template #default="{ row }">
              <span v-if="row.points?.length" :style="{ color: row.points.at(-1)! >= 100 ? '#67C23A' : '#F56C6C' }">
                {{ row.points.at(-1)! >= 100 ? '+' : '' }}{{ row.points.at(-1)! - 100 }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="90">
            <template #default="{ row }">{{ ((row.confidence ?? 0) * 100).toFixed(0) }}%</template>
          </el-table-column>
          <el-table-column label="关联岗位" min-width="200">
            <template #default="{ row }">
              <el-tag v-for="pos in row.related_positions" :key="pos" size="small" class="related-tag">{{ pos }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 演化详情抽屉 -->
      <el-drawer v-model="drawerVisible" :title="`${selectedSkillForDetail} 演化历史`" size="400px">
        <div v-loading="changelogLoading">
          <el-timeline v-if="changelogData.length">
            <el-timeline-item v-for="(item, idx) in changelogData" :key="idx" :timestamp="item.date ?? item.created_at ?? ''" placement="top">
              <el-card shadow="never">
                <p><b>{{ item.change_type ?? '变更' }}</b>: {{ item.description ?? item.detail ?? '' }}</p>
                <p v-if="item.trust_score" style="color: #909399; font-size: 12px;">信任度: {{ (item.trust_score * 100).toFixed(0) }}%</p>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无演化记录" />
        </div>
      </el-drawer>
    </div>
  </MainLayout>
</template>

<style scoped>
.evolution-page {
  min-height: 400px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 4px;
  font-size: 22px;
  color: #303133;
}

.subtitle {
  margin: 0;
  font-size: 14px;
  color: #909399;
}

/* KPI 行 */
.kpi-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
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
  gap: 10px;
}

.emerging-item {
  padding: 10px 12px;
  background: linear-gradient(135deg, #f0fff4 0%, #e8f5e9 100%);
  border: 1px solid #c8e6c9;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.emerging-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.2);
}

.emerging-name {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.emerging-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.emerging-cii {
  font-size: 12px;
  color: #67C23A;
  font-weight: 500;
}

/* 脉冲动画标签 */
.pulse-tag {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.chart-card {
  margin-bottom: 20px;
}

/* 技能对比 */
.compare-card {
  margin-bottom: 20px;
}

.compare-selectors {
  display: flex;
  align-items: center;
  gap: 12px;
}

.compare-vs {
  font-size: 16px;
  font-weight: 700;
  color: #909399;
}

.compare-placeholder {
  text-align: center;
  padding: 40px;
  color: #c0c4cc;
  font-size: 14px;
}

.table-card {
  margin-bottom: 20px;
}

.related-tag {
  margin-right: 6px;
  margin-bottom: 4px;
}

@media (max-width: 768px) {
  .kpi-row {
    flex-direction: column;
  }
  .gauge-card {
    flex: 1;
  }
  .compare-selectors {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
