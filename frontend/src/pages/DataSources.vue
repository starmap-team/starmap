<script setup lang="ts">
/**
 * 数据源管理页 — Sprint 1.2
 * 网格卡片布局展示5个数据源（BOSS/拉勾/51Job/GitHub/ESCO）
 * 每个卡片含：权威度评分环形图、日采集量柱状图、数据质量评分、最后同步时间、一键同步按钮
 */
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight, Loading as LoadingIcon } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GaugeChart, BarChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
} from 'echarts/components'
import MainLayout from '@/layouts/MainLayout.vue'
import { useDataSourceStore } from '@/stores/datasource'
import type { DataSourceDetail } from '@/stores/datasource'
import { chartColors, tooltipStyle, splitLineStyle, axisLabelStyle } from '@/utils/chartTheme'

use([GaugeChart, BarChart, TooltipComponent, GridComponent])

const dsStore = useDataSourceStore()

const syncingIds = ref<Set<string>>(new Set())

onMounted(() => {
  dsStore.fetchSources()
})

// ── 权威度环形图配置 ──
function getAuthorityGaugeOption(score: number) {
  const colors = chartColors()
  const pct = Math.round(score * 100)
  let color = colors.danger
  if (pct >= 80) color = colors.success
  else if (pct >= 60) color = colors.warning

  return {
    series: [{
      type: 'gauge',
      startAngle: 220,
      endAngle: -40,
      radius: '90%',
      center: ['50%', '55%'],
      min: 0,
      max: 100,
      progress: { show: true, width: 10, roundCap: true, itemStyle: { color } },
      axisLine: { lineStyle: { width: 10, color: [[1, colors.border]] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      pointer: { show: false },
      detail: {
        valueAnimation: true,
        formatter: '{value}',
        fontSize: 20,
        fontWeight: 700,
        color: colors.foreground,
        offsetCenter: [0, '10%'],
      },
      title: {
        show: true,
        offsetCenter: [0, '40%'],
        fontSize: 10,
        color: colors.muted,
      },
      data: [{ value: pct, name: '权威度' }],
    }],
  }
}

// ── 日采集量柱状图配置 ──
function getDailyVolumeOption(volumes: number[]) {
  const colors = chartColors()
  const days = ['一', '二', '三', '四', '五', '六', '日']
  return {
    tooltip: {
      ...tooltipStyle(),
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    grid: { top: 8, bottom: 20, left: 28, right: 8 },
    xAxis: {
      type: 'category',
      data: volumes.map((_, i) => days[i] ?? `D${i + 1}`),
      axisLabel: { ...axisLabelStyle(), fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      splitLine: splitLineStyle(),
      axisLabel: { ...axisLabelStyle(), fontSize: 9 },
    },
    series: [{
      type: 'bar',
      data: volumes.map((v, i) => ({
        value: v,
        itemStyle: {
          color: i === volumes.length - 1 ? colors.primary : colors.primary + '60',
          borderRadius: [3, 3, 0, 0],
        },
      })),
      barWidth: '55%',
    }],
  }
}

// ── 数据源状态映射 ──
function getStatusBadge(status: string) {
  switch (status) {
    case 'active':  return { type: 'success', label: '运行中' }
    case 'paused':  return { type: 'warning', label: '已暂停' }
    case 'error':   return { type: 'danger',  label: '异常' }
    default:        return { type: 'info',    label: '未知' }
  }
}

function getSourceTypeLabel(type: string) {
  const map: Record<string, string> = { crawler: '爬虫', api: 'API', manual: '手动', import: '导入' }
  return map[type] ?? type
}

function formatLastCrawl(dateStr: string) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min}分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}小时前`
  const day = Math.floor(hr / 24)
  return `${day}天前`
}

function formatRecords(n: number) {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

// ── 一键同步 ──
async function handleSync(source: DataSourceDetail) {
  if (syncingIds.value.has(source.id)) return
  syncingIds.value.add(source.id)
  try {
    const ok = await dsStore.triggerSync(source.id)
    if (ok) {
      ElMessage.success(`${source.name} 同步已触发`)
    } else {
      ElMessage.error(`${source.name} 同步失败`)
    }
  } catch {
    ElMessage.error(`${source.name} 同步失败`)
  } finally {
    syncingIds.value.delete(source.id)
  }
}

// ── 汇总统计 ──
const summaryStats = computed(() => {
  const src = dsStore.sources
  return {
    total: src.length,
    active: src.filter(s => s.status === 'active').length,
    totalRecords: src.reduce((sum, s) => sum + s.total_records, 0),
    avgQuality: src.length
      ? (src.reduce((sum, s) => sum + s.avg_quality_score, 0) / src.length)
      : 0,
  }
})
</script>

<template>
  <MainLayout>
    <div class="datasources-page animate-fade-in">
      <!-- 页面头部 -->
      <div class="page-header">
        <div>
          <h2>数据源管理</h2>
          <p class="page-desc">
            管理多源数据融合：BOSS直聘 / 拉勾 / 51Job / GitHub / ESCO
          </p>
        </div>
        <div class="header-actions">
          <el-button
            size="small"
            :icon="RefreshRight"
            :loading="dsStore.loading"
            @click="dsStore.fetchSources()"
          >
            刷新
          </el-button>
        </div>
      </div>

      <!-- 汇总 KPI -->
      <el-row
        :gutter="16"
        class="mb-4"
      >
        <el-col
          :lg="6"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="kpi-card"
          >
            <div class="kpi-inner">
              <div
                class="kpi-icon"
                :style="{ background: chartColors().primary + '18', color: chartColors().primary }"
              >
                <el-icon size="22">
                  <Connection />
                </el-icon>
              </div>
              <div class="kpi-body">
                <div class="kpi-label">数据源总数</div>
                <div
                  class="kpi-value"
                  :style="{ color: chartColors().primary }"
                >
                  {{ summaryStats.total }}
                </div>
                <div class="kpi-sub">{{ summaryStats.active }} 个活跃</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col
          :lg="6"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="kpi-card"
          >
            <div class="kpi-inner">
              <div
                class="kpi-icon"
                :style="{ background: chartColors().success + '18', color: chartColors().success }"
              >
                <el-icon size="22">
                  <Coin />
                </el-icon>
              </div>
              <div class="kpi-body">
                <div class="kpi-label">总记录量</div>
                <div
                  class="kpi-value"
                  :style="{ color: chartColors().success }"
                >
                  {{ formatRecords(summaryStats.totalRecords) }}
                </div>
                <div class="kpi-sub">条已入库</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col
          :lg="6"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="kpi-card"
          >
            <div class="kpi-inner">
              <div
                class="kpi-icon"
                :style="{ background: chartColors().info + '18', color: chartColors().info }"
              >
                <el-icon size="22">
                  <DataLine />
                </el-icon>
              </div>
              <div class="kpi-body">
                <div class="kpi-label">平均质量分</div>
                <div
                  class="kpi-value"
                  :style="{ color: summaryStats.avgQuality >= 0.8 ? chartColors().success : chartColors().warning }"
                >
                  {{ (summaryStats.avgQuality * 100).toFixed(1) }}%
                </div>
                <div class="kpi-sub">
                  <span :class="summaryStats.avgQuality >= 0.8 ? 'trend-up' : 'trend-down'">
                    {{ summaryStats.avgQuality >= 0.8 ? '▲' : '▼' }}
                  </span>
                  {{ summaryStats.avgQuality >= 0.8 ? '质量优秀' : '有提升空间' }}
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col
          :lg="6"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="kpi-card"
          >
            <div class="kpi-inner">
              <div
                class="kpi-icon"
                :style="{ background: chartColors().warning + '18', color: chartColors().warning }"
              >
                <el-icon size="22">
                  <WarningFilled />
                </el-icon>
              </div>
              <div class="kpi-body">
                <div class="kpi-label">异常数据源</div>
                <div
                  class="kpi-value"
                  :style="{ color: summaryStats.total - summaryStats.active > 0 ? chartColors().danger : chartColors().success }"
                >
                  {{ summaryStats.total - summaryStats.active }}
                </div>
                <div class="kpi-sub">
                  {{ summaryStats.total - summaryStats.active > 0 ? '需关注' : '全部正常' }}
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 数据源卡片网格 -->
      <el-row
        v-loading="dsStore.loading"
        :gutter="16"
      >
        <el-col
          v-for="source in dsStore.sources"
          :key="source.id"
          :xl="8"
          :lg="12"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="source-card"
          >
            <!-- 卡片头部 -->
            <div class="card-header">
              <div class="card-title-group">
                <span class="card-name">{{ source.name }}</span>
                <el-tag
                  :type="getStatusBadge(source.status).type as any"
                  size="small"
                  effect="light"
                  round
                >
                  {{ getStatusBadge(source.status).label }}
                </el-tag>
              </div>
              <el-tag
                size="small"
                effect="plain"
                round
              >
                {{ getSourceTypeLabel(source.source_type) }}
              </el-tag>
            </div>

            <!-- 权威度环形图 + 统计信息 -->
            <div class="card-body">
              <div class="card-gauge">
                <VChart
                  :option="getAuthorityGaugeOption(source.authority_score)"
                  style="width: 130px; height: 110px;"
                  autoresize
                />
              </div>
              <div class="card-stats">
                <div class="stat-row">
                  <span class="stat-label">数据质量</span>
                  <span
                    class="stat-value"
                    :style="{ color: source.avg_quality_score >= 0.8 ? chartColors().success : chartColors().warning }"
                  >{{ (source.avg_quality_score * 100).toFixed(0) }}%</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">记录总量</span>
                  <span class="stat-value">{{ formatRecords(source.total_records) }}</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">有效记录</span>
                  <span class="stat-value">{{ source.valid_records.toLocaleString() }}</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">重复率</span>
                  <span
                    class="stat-value"
                    :style="{ color: source.duplicate_rate > 0.2 ? chartColors().danger : chartColors().success }"
                  >{{ (source.duplicate_rate * 100).toFixed(1) }}%</span>
                </div>
              </div>
            </div>

            <!-- 日采集量柱状图 -->
            <div class="card-chart">
              <div class="chart-label">
                日采集量
              </div>
              <VChart
                v-if="source.daily_crawl_volume?.length"
                :option="getDailyVolumeOption(source.daily_crawl_volume)"
                style="height: 100px;"
                autoresize
              />
              <div
                v-else
                class="chart-placeholder"
              >
                <span>暂无采集数据</span>
              </div>
            </div>

            <!-- 底部：同步时间 + 操作按钮 -->
            <div class="card-footer">
              <span class="sync-time">
                最后同步：{{ formatLastCrawl(source.last_crawl_at) }}
              </span>
              <el-button
                size="small"
                type="primary"
                :loading="syncingIds.has(source.id)"
                :disabled="source.status === 'paused'"
                @click="handleSync(source)"
              >
                <el-icon
                  v-if="!syncingIds.has(source.id)"
                  class="el-icon--left"
                >
                  <RefreshRight />
                </el-icon>
                {{ syncingIds.has(source.id) ? '同步中...' : '一键同步' }}
              </el-button>
            </div>
          </el-card>
        </el-col>

        <!-- 空状态 -->
        <el-col
          v-if="!dsStore.loading && !dsStore.sources.length"
          :span="24"
        >
          <el-card
            shadow="never"
            class="empty-card"
          >
            <div class="custom-empty">
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
                >
                  <ellipse cx="12" cy="5" rx="9" ry="3" />
                  <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
                  <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
                </svg>
              </div>
              <p class="empty-text">数据源待加载</p>
              <p class="empty-hint-text">数据源信息将在首次同步后展示</p>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </MainLayout>
</template>

<style scoped>
.datasources-page {
  max-width: 1200px;
  margin: 0 auto;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-6);
  flex-wrap: wrap;
  gap: var(--space-3);
}
.page-header h2 {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  color: var(--foreground);
  margin: 0 0 var(--space-1);
  letter-spacing: var(--tracking-tight);
}
.page-desc {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
  margin: 0;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

/* KPI 卡片 */
.kpi-card {
  cursor: default;
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}
.kpi-card::before {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 4%, transparent), transparent);
  transition: opacity var(--duration-normal);
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.kpi-card:hover::before { opacity: 1; }
.kpi-inner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  position: relative;
  z-index: 1;
}
.kpi-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-xl);
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
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  font-weight: 500;
}
.kpi-value {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: var(--tracking-tight);
  font-variant-numeric: tabular-nums;
}
.kpi-sub {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  margin-top: var(--space-1);
}
.trend-up {
  color: var(--success);
  font-weight: 600;
}
.trend-down {
  color: var(--destructive);
  font-weight: 600;
}

/* 数据源卡片 */
.source-card {
  transition: all var(--duration-normal) var(--ease-out);
  height: 100%;
}
.source-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
  gap: var(--space-2);
}
.card-title-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.card-name {
  font-size: var(--font-size-lg);
  font-weight: 700;
  color: var(--foreground);
  letter-spacing: var(--tracking-tight);
}

/* 卡片主体：权威度 + 统计 */
.card-body {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.card-gauge {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.card-stats {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.stat-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
.stat-value {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--foreground);
  font-variant-numeric: tabular-nums;
}

/* 日采集量图表 */
.card-chart {
  margin-bottom: var(--space-3);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
}
.chart-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--muted-foreground);
  margin-bottom: var(--space-1);
}
.chart-placeholder {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted-foreground);
  font-size: var(--font-size-xs);
  opacity: 0.5;
}

/* 卡片底部 */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
}
.sync-time {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

/* 空状态 */
.empty-card {
  min-height: 300px;
}
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-8) var(--space-4);
  text-align: center;
}
.empty-icon-wrapper {
  color: var(--muted-foreground);
  opacity: 0.4;
  margin-bottom: var(--space-3);
}
.empty-text {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
}
.empty-hint-text {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}

.mb-4 { margin-bottom: var(--space-4); }

/* 响应式 */
@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .header-actions { width: 100%; justify-content: flex-start; }
  .kpi-value { font-size: var(--font-size-2xl); }
  .card-body { flex-direction: column; text-align: center; }
  .card-stats { width: 100%; }
}
</style>
