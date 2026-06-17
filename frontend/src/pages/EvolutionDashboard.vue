<script setup lang="ts">
/**
 * 演化看板页 — CII 时序曲线（技能需求通胀指数）
 */
import { ref, onMounted, computed } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import MainLayout from '@/layouts/MainLayout.vue'

use([CanvasRenderer, LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

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

const trendLabel: Record<string, string> = { rising: '↑ 上升', stable: '→ 平稳', declining: '↓ 下降' }
const trendTagType: Record<string, string> = { rising: 'success', stable: 'info', declining: 'danger' }
const SERIES_COLORS = ['#E040FB', '#36CFC9', '#409EFF', '#67C23A', '#F56C6C']

async function fetchTrends() {
  loading.value = true
  const resp = await fetch('/api/v1/evolution/trends')
  const data = await resp.json()
  quarters.value = data.quarters ?? []
  items.value = data.items ?? []
  loading.value = false
}

const chartOption = computed(() => {
  const filtered = selectedSkill.value
    ? items.value.filter(i => i.skill_name === selectedSkill.value)
    : items.value

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
        <el-select
          v-model="selectedSkill"
          placeholder="全部技能"
          clearable
          size="small"
          style="width: 160px"
        >
          <el-option
            v-for="item in items"
            :key="item.skill_name"
            :label="item.skill_name"
            :value="item.skill_name"
          />
        </el-select>
      </div>

      <!-- 曲线图 -->
      <el-card v-loading="loading" class="chart-card">
        <v-chart
          v-if="items.length"
          :option="chartOption"
          autoresize
          style="height: 420px"
        />
        <el-empty v-else description="暂无演化数据" />
      </el-card>

      <!-- 趋势概览表 -->
      <el-card class="table-card">
        <template #header>趋势概览</template>
        <el-table :data="items" size="small" stripe>
          <el-table-column prop="skill_name" label="技能" min-width="120" />
          <el-table-column label="趋势" width="100">
            <template #default="{ row }">
              <el-tag :type="trendTagType[row.trend]" size="small" effect="plain">
                {{ trendLabel[row.trend] ?? row.trend }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="当前 CII" width="100">
            <template #default="{ row }">
              <b>{{ row.points?.[row.points.length - 1] ?? '-' }}</b>
            </template>
          </el-table-column>
          <el-table-column label="变化" width="100">
            <template #default="{ row }">
              <span
                v-if="row.points?.length"
                :style="{ color: row.points.at(-1)! >= 100 ? '#67C23A' : '#F56C6C' }"
              >
                {{ row.points.at(-1)! >= 100 ? '+' : '' }}{{ row.points.at(-1)! - 100 }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="90">
            <template #default="{ row }">
              {{ ((row.confidence ?? 0) * 100).toFixed(0) }}%
            </template>
          </el-table-column>
          <el-table-column label="关联岗位" min-width="200">
            <template #default="{ row }">
              <el-tag
                v-for="pos in row.related_positions"
                :key="pos"
                size="small"
                class="related-tag"
              >{{ pos }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
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

.chart-card {
  margin-bottom: 20px;
}

.table-card {
  margin-bottom: 20px;
}

.related-tag {
  margin-right: 6px;
  margin-bottom: 4px;
}
</style>
