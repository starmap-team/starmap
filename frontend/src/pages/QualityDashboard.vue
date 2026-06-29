<script setup lang="ts">
/**
 * 图谱质量仪表盘 — R6 曾洋涛
 * 4 指标卡（含趋势箭头）+ 信任度直方图 + 幻觉率趋势 + 数据源饼图 + 审核队列
 */
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useQualityStore } from '@/stores/quality'

const quality = useQualityStore()

// 自动刷新
const autoRefresh = ref(true)
const refreshInterval = ref(30) // 秒
let timer: ReturnType<typeof setInterval> | null = null
const lastRefresh = ref('')

function startAutoRefresh() {
  if (timer) clearInterval(timer)
  if (autoRefresh.value) {
    timer = setInterval(() => {
      quality.fetchQuality().then(() => {
        lastRefresh.value = new Date().toLocaleTimeString()
      })
    }, refreshInterval.value * 1000)
  }
}

onMounted(() => {
  quality.fetchQuality().then(() => {
    lastRefresh.value = new Date().toLocaleTimeString()
  })
  startAutoRefresh()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

function toggleAutoRefresh(val: boolean) {
  autoRefresh.value = val
  if (val) {
    startAutoRefresh()
    ElMessage.success(`已开启自动刷新（每${refreshInterval.value}秒）`)
  } else {
    if (timer) clearInterval(timer)
    ElMessage.info('已关闭自动刷新')
  }
}

// ── KPI 卡片（含趋势箭头）──
const kpiCardsEnhanced = computed(() => {
  if (!quality.metrics) return []
  const m = quality.metrics
  return [
    {
      label: '总节点数',
      value: m.total_nodes.toLocaleString(),
      sub: `周新增 +${m.weekly_new_nodes}`,
      trend: 'up',
      color: '#409eff',
      icon: 'Grid',
    },
    {
      label: '平均信任度',
      value: (m.avg_trust_score * 100).toFixed(1) + '%',
      sub: `高信任占比 ${(m.high_trust_ratio * 100).toFixed(0)}%`,
      trend: m.avg_trust_score >= 0.75 ? 'up' : 'down',
      color: '#67c23a',
      icon: 'DataLine',
    },
    {
      label: '幻觉率',
      value: (m.hallucination_rate * 100).toFixed(1) + '%',
      sub: `审核通过率 ${(m.audit_pass_rate * 100).toFixed(0)}%`,
      trend: m.hallucination_rate <= 0.08 ? 'down' : 'up',
      color: '#e6a23c',
      icon: 'WarningFilled',
    },
    {
      label: '待审核',
      value: String(m.pending_review),
      sub: '条记录待处理',
      trend: m.pending_review > 5 ? 'up' : 'down',
      color: '#f56c6c',
      icon: 'Clock',
    },
  ]
})

// ── 信任度分布直方图 ──
const histogramOption = computed(() => {
  if (!quality.metrics?.trust_distribution) return {}
  const dist = quality.metrics.trust_distribution
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    grid: { top: 16, bottom: 36, left: 48, right: 16 },
    xAxis: {
      type: 'category',
      name: '信任度区间',
      data: dist.map(d => d.range),
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: '节点数',
    },
    series: [{
      type: 'bar',
      data: dist.map((d, i) => ({
        value: d.count,
        itemStyle: {
          color: ['#f56c6c', '#f89898', '#e6a23c', '#67c23a', '#409eff', '#409eff'][i],
          borderRadius: [4, 4, 0, 0],
        },
      })),
      barWidth: '65%',
      label: {
        show: true,
        position: 'top',
        fontSize: 11,
        color: '#606266',
      },
    }],
  }
})

// ── 幻觉趋势 + 预警线 ──
const trendChartOption = computed(() => {
  if (!quality.metrics?.hallucination_trend) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { top: 20, bottom: 28, left: 50, right: 20 },
    xAxis: { type: 'category', data: quality.metrics.hallucination_trend.map(t => t.date) },
    yAxis: {
      type: 'value',
      name: '幻觉率 (%)',
      min: 0,
      max: 20,
    },
    series: [{
      type: 'line',
      data: quality.metrics.hallucination_trend.map(t => ({
        value: +(t.rate * 100).toFixed(1),
      })),
      smooth: true,
      areaStyle: { opacity: 0.12, color: '#e6a23c' },
      lineStyle: { color: '#e6a23c', width: 2.5 },
      itemStyle: { color: '#e6a23c' },
      symbolSize: 6,
      markLine: {
        silent: true,
        symbol: 'none',
        data: [{
          yAxis: 10,
          label: { formatter: '预警线 10%', fontSize: 11 },
          lineStyle: { color: '#f56c6c', type: 'dashed', width: 2 },
        }],
      },
    }],
  }
})

// ── 数据源饼图 ──
const sourceChartOption = computed(() => {
  if (!quality.metrics?.source_distribution) return {}
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 条 ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['48%', '75%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 4,
        borderColor: '#fff',
        borderWidth: 2,
      },
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 12, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.25)' },
      },
      data: quality.metrics.source_distribution.map(s => ({
        name: s.name,
        value: s.count,
      })),
    }],
  }
})
</script>

<template>
  <MainLayout>
    <div class="quality-page">
      <div class="page-header">
        <div>
          <h2>图谱质量仪表盘</h2>
          <p class="page-desc">
            实时监控数据质量、信任度分布与幻觉率趋势
          </p>
        </div>
        <div class="header-actions">
          <span
            v-if="lastRefresh"
            class="last-refresh"
          >最近刷新：{{ lastRefresh }}</span>
          <el-switch
            v-model="autoRefresh"
            active-text="自动刷新"
            size="small"
            @change="toggleAutoRefresh"
          />
          <el-button
            size="small"
            :icon="RefreshRight"
            @click="quality.fetchQuality(); lastRefresh = new Date().toLocaleTimeString()"
          >
            刷新
          </el-button>
        </div>
      </div>

      <!-- 4 指标卡（含趋势） -->
      <el-row
        :gutter="16"
        style="margin-bottom: 16px"
      >
        <el-col
          v-for="card in kpiCardsEnhanced"
          :key="card.label"
          :lg="6"
          :md="12"
          :sm="24"
          style="margin-bottom: 16px"
        >
          <el-card
            shadow="hover"
            class="kpi-card"
          >
            <div class="kpi-inner">
              <div
                class="kpi-icon"
                :style="{ background: card.color + '18', color: card.color }"
              >
                <el-icon size="22">
                  <component :is="card.icon" />
                </el-icon>
              </div>
              <div class="kpi-body">
                <div class="kpi-label">
                  {{ card.label }}
                </div>
                <div
                  class="kpi-value"
                  :style="{ color: card.color }"
                >
                  {{ card.value }}
                </div>
                <div class="kpi-sub">
                  <span :class="card.trend === 'up' ? 'trend-up' : 'trend-down'">
                    {{ card.trend === 'up' ? '▲' : '▼' }}
                  </span>
                  {{ card.sub }}
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 直方图 + 趋势 -->
      <el-row
        :gutter="16"
        style="margin-bottom: 16px"
      >
        <el-col
          :lg="12"
          :sm="24"
          style="margin-bottom: 16px"
        >
          <el-card
            v-loading="quality.loading"
            shadow="never"
            header="信任度分布直方图"
          >
            <v-chart
              v-if="quality.metrics?.trust_distribution"
              :option="histogramOption"
              style="height: 330px"
              autoresize
            />
            <el-empty
              v-else
              description="暂无数据"
              :image-size="80"
            />
          </el-card>
        </el-col>
        <el-col
          :lg="12"
          :sm="24"
          style="margin-bottom: 16px"
        >
          <el-card
            v-loading="quality.loading"
            shadow="never"
            header="幻觉率趋势"
          >
            <v-chart
              v-if="quality.metrics?.hallucination_trend"
              :option="trendChartOption"
              style="height: 330px"
              autoresize
            />
            <el-empty
              v-else
              description="暂无数据"
              :image-size="80"
            />
          </el-card>
        </el-col>
      </el-row>

      <!-- 数据源 + 审核 -->
      <el-row :gutter="16">
        <el-col
          :lg="12"
          :sm="24"
          style="margin-bottom: 16px"
        >
          <el-card
            v-loading="quality.loading"
            shadow="never"
            header="数据源贡献分布"
          >
            <v-chart
              v-if="quality.metrics?.source_distribution"
              :option="sourceChartOption"
              style="height: 310px"
              autoresize
            />
            <el-empty
              v-else
              description="暂无数据源信息"
              :image-size="80"
            />
          </el-card>
        </el-col>
        <el-col
          :lg="12"
          :sm="24"
          style="margin-bottom: 16px"
        >
          <el-card
            v-loading="quality.loading"
            shadow="never"
            header="待审核队列"
          >
            <el-table
              :data="quality.metrics?.audit_queue ?? []"
              stripe
              size="small"
              max-height="310"
              empty-text="暂无待审核数据"
            >
              <el-table-column
                prop="id"
                label="#"
                width="50"
                align="center"
              />
              <el-table-column
                prop="position"
                label="岗位"
              />
              <el-table-column
                prop="skill"
                label="技能"
              />
              <el-table-column
                prop="trust"
                label="信任度"
                width="120"
                align="center"
              >
                <template #default="{ row }">
                  <el-progress
                    :percentage="row.trust"
                    :stroke-width="8"
                    :color="row.trust >= 70 ? '#67c23a' : row.trust >= 50 ? '#e6a23c' : '#f56c6c'"
                  />
                </template>
              </el-table-column>
              <el-table-column
                label="操作"
                width="150"
                align="center"
              >
                <template #default>
                  <el-button
                    size="small"
                    type="success"
                    plain
                  >
                    通过
                  </el-button>
                  <el-button
                    size="small"
                    type="danger"
                    plain
                  >
                    拒绝
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </MainLayout>
</template>

<style scoped>
.quality-page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}

.page-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 4px;
}

.page-desc {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.last-refresh {
  font-size: 12px;
  color: #c0c4cc;
}

/* ── KPI 卡片 ── */
.kpi-card {
  cursor: default;
  transition: transform 0.2s, box-shadow 0.2s;
}

.kpi-card:hover {
  transform: translateY(-2px);
}

.kpi-inner {
  display: flex;
  align-items: center;
  gap: 14px;
}

.kpi-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.kpi-body {
  flex: 1;
  min-width: 0;
}

.kpi-label {
  font-size: 13px;
  color: #909399;
}

.kpi-value {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.3;
}

.kpi-sub {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.trend-up {
  color: #67c23a;
  font-weight: bold;
}

.trend-down {
  color: #f56c6c;
  font-weight: bold;
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .kpi-value {
    font-size: 22px;
  }
}
</style>
