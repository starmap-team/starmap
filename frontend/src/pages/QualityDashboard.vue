<script setup lang="ts">
/**
 * 图谱质量仪表盘 — R6 曾洋涛
 * 4 指标卡（含趋势箭头）+ 信任度直方图 + 幻觉率趋势 + 数据源饼图 + 审核队列
 */
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useQualityStore } from '@/stores/quality'
import { useAuditStore } from '@/stores/audit'
import { chartColors } from '@/utils/chartTheme'
import QualityTrendChart from '@/components/QualityTrendChart.vue'
import AlertList from '@/components/AlertList.vue'
import { useQualityDashboardCharts } from '@/composables/useQualityDashboardCharts'
import { useQualityActions } from '@/composables/useQualityActions'
import { useQualityDashboard } from '@/composables/useQualityDashboard'

const quality = useQualityStore()
const audit = useAuditStore()
// ponytail: chartColors re-exported for template el-progress :color binding
const cc = chartColors()
const {
  kpiCardsEnhanced,
  histogramOption,
  trendChartOption,
  sourceChartOption,
} = useQualityDashboardCharts(quality)

// Page-level orchestration (activeTab + auto-refresh + initial fetch — Phase 7 D round 11)
const {
  activeTab,
  autoRefresh,
  lastRefresh,
  toggleAutoRefresh,
} = useQualityDashboard(quality)

// 趋势周期 / 告警 操作
const {
  trendPeriod,
  handleTrendPeriodChange,
  handleResolveAlert,
  handleIgnoreAlert,
} = useQualityActions(quality)

// ponytail: 原模板内联 `quality.fetchQuality(); lastRefresh=...` 未 await，
// 请求失败也显示"已刷新"；改为 await 后成功才置位，失败提示
async function handleRefresh() {
  try {
    await quality.fetchQuality()
    lastRefresh.value = new Date().toLocaleTimeString()
  } catch (err: unknown) {
    ElMessage.error('刷新失败：' + (err instanceof Error ? err.message : '未知错误'))
  }
}
</script>

<template>
  <MainLayout>
    <div class="quality-page animate-fade-in">
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
            @click="handleRefresh"
          >
            刷新
          </el-button>
        </div>
      </div>

      <!-- 4 指标卡（含趋势） -->
      <el-row
        :gutter="16"
        class="mb-4"
      >
        <el-col
          v-for="card in kpiCardsEnhanced"
          :key="card.label"
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

      <!-- Phase 13 数据诚实化：抽取质量基线。无 golden-set 基线时显“未评估”说明，
           有基线时才呈现 precision/recall/F1，避免 0/0/0 被误读为红色/失败或静默缺失。 -->
      <el-alert
        v-if="quality.metrics && quality.metrics.baseline_available === false"
        type="info"
        :closable="false"
        show-icon
        class="mb-4"
        title="抽取质量（precision / recall / F1）暂未评估"
        :description="quality.metrics.evaluation_explanation || '尚未运行 golden-set 评估，质量指标暂不可信；此处不显示红色/失败态以免误导。请调用 /quality/evaluate 建立基线。'"
      />
      <el-card
        v-else-if="quality.metrics"
        shadow="never"
        class="mb-4"
        :header="'抽取质量（golden-set 评估） · ' + (quality.metrics.warning_level || '')"
      >
        <div style="display: flex; gap: 24px; flex-wrap: wrap">
          <div>
            <strong style="font-size: 20px">{{ (quality.metrics.precision * 100).toFixed(1) }}%</strong>
            <div style="color: var(--muted-foreground); font-size: 12px">
              Precision
            </div>
          </div>
          <div>
            <strong style="font-size: 20px">{{ (quality.metrics.recall * 100).toFixed(1) }}%</strong>
            <div style="color: var(--muted-foreground); font-size: 12px">
              Recall
            </div>
          </div>
          <div>
            <strong style="font-size: 20px">{{ (quality.metrics.f1 * 100).toFixed(1) }}%</strong>
            <div style="color: var(--muted-foreground); font-size: 12px">
              F1
            </div>
          </div>
        </div>
      </el-card>

      <!-- 直方图 + 趋势 -->
      <el-row
        :gutter="16"
        class="mb-4"
      >
        <el-col
          :lg="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            v-loading="quality.loading"
            shadow="never"
            header="信任度分布直方图"
          >
            <v-chart
              v-if="quality.metrics?.trust_distribution"
              :option="histogramOption"
              class="chart-h-md"
              autoresize
            />
            <div
              v-if="quality.loading || !quality.metrics"
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
              </div>
              <p class="starmap-empty">
                {{ quality.loading ? '数据加载中' : '暂无数据' }}
              </p>
              <p class="starmap-empty--hint">
                图谱质量指标将在评估完成后展示
              </p>
            </div>
          </el-card>
        </el-col>
        <el-col
          :lg="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            v-loading="quality.loading"
            shadow="never"
            header="幻觉率趋势"
          >
            <v-chart
              v-if="quality.metrics?.hallucination_trend"
              :option="trendChartOption"
              class="chart-h-md"
              autoresize
            />
            <div
              v-if="quality.loading || !quality.metrics"
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
              </div>
              <p class="starmap-empty">
                {{ quality.loading ? '数据加载中' : '暂无数据' }}
              </p>
              <p class="starmap-empty--hint">
                图谱质量指标将在评估完成后展示
              </p>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 数据源 + 审核 -->
      <el-row :gutter="16">
        <el-col
          :lg="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            v-loading="quality.loading"
            shadow="never"
            header="数据源贡献分布"
          >
            <v-chart
              v-if="quality.metrics?.source_distribution"
              :option="sourceChartOption"
              class="chart-h-sm"
              autoresize
            />
            <div
              v-if="quality.loading || !quality.metrics"
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
                ><line
                  x1="8"
                  y1="6"
                  x2="21"
                  y2="6"
                /><line
                  x1="8"
                  y1="12"
                  x2="21"
                  y2="12"
                /><line
                  x1="8"
                  y1="18"
                  x2="21"
                  y2="18"
                /><line
                  x1="3"
                  y1="6"
                  x2="3.01"
                  y2="6"
                /><line
                  x1="3"
                  y1="12"
                  x2="3.01"
                  y2="12"
                /><line
                  x1="3"
                  y1="18"
                  x2="3.01"
                  y2="18"
                /></svg>
              </div>
              <p class="starmap-empty">
                数据源信息待同步
              </p>
            </div>
          </el-card>
        </el-col>
        <el-col
          :lg="12"
          :sm="24"
          class="mb-4"
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
              empty-text="队列为空，暂无待审核项"
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
                    :color="row.trust >= 70 ? cc.success : row.trust >= 50 ? cc.warning : cc.danger"
                  />
                </template>
              </el-table-column>
              <el-table-column
                label="操作"
                width="150"
                align="center"
              >
                <template #default="{ row }">
                  <el-button
                    size="small"
                    type="success"
                    plain
                    @click="audit.approveAudit(row.id).catch(() => ElMessage.error('审批失败'))"
                  >
                    通过
                  </el-button>
                  <el-button
                    size="small"
                    type="danger"
                    plain
                    @click="audit.rejectAudit(row.id).catch(() => ElMessage.error('拒绝失败'))"
                  >
                    拒绝
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <!-- Sprint 1.2: 质量趋势 + 异常告警 Tabs -->
      <el-card
        shadow="never"
        class="mb-4 tabs-card"
      >
        <el-tabs
          v-model="activeTab"
          class="quality-tabs"
        >
          <!-- 质量趋势 Tab -->
          <el-tab-pane
            label="质量趋势"
            name="trend"
          >
            <div class="trend-controls">
              <el-radio-group
                v-model="trendPeriod"
                size="small"
                @change="handleTrendPeriodChange"
              >
                <el-radio-button value="7d">
                  7天
                </el-radio-button>
                <el-radio-button value="30d">
                  30天
                </el-radio-button>
                <el-radio-button value="90d">
                  90天
                </el-radio-button>
              </el-radio-group>
            </div>
            <div v-loading="quality.loading">
              <QualityTrendChart
                :data="quality.trends"
                :period="trendPeriod"
              />
            </div>
          </el-tab-pane>

          <!-- 异常告警 Tab -->
          <el-tab-pane
            label="异常告警"
            name="alert"
          >
            <div
              v-loading="quality.alertsLoading"
              class="alert-section"
            >
              <div class="alert-summary">
                <el-tag
                  :type="quality.alerts.filter(a => a.status === 'pending').length > 0 ? 'danger' : 'success'"
                  size="small"
                  effect="light"
                  round
                >
                  {{ quality.alerts.filter(a => a.status === 'pending').length }} 条待处理
                </el-tag>
                <el-tag
                  type="info"
                  size="small"
                  effect="plain"
                  round
                >
                  共 {{ quality.alerts.length }} 条告警
                </el-tag>
              </div>
              <AlertList
                :alerts="quality.alerts"
                @resolve="handleResolveAlert"
                @ignore="handleIgnoreAlert"
              />
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
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
.last-refresh {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
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
@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .header-actions { width: 100%; justify-content: flex-start; }
  .kpi-value { font-size: var(--font-size-2xl); }
}
.mb-4 { margin-bottom: var(--space-4); }
.chart-h-md { height: 330px; }
.chart-h-sm { height: 310px; }

.custom-empty { display: flex; flex-direction: column; align-items: center; padding: var(--space-8) var(--space-4); text-align: center; }
.empty-icon-wrapper { color: var(--muted-foreground); opacity: 0.4; margin-bottom: var(--space-3); }

/* Sprint 1.2: Tabs */
.tabs-card :deep(.el-card__body) {
  padding-top: 0;
}
.quality-tabs :deep(.el-tabs__header) {
  margin-bottom: var(--space-4);
}
.trend-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-bottom: var(--space-3);
}
.alert-section {
  min-height: 200px;
}
.alert-summary {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
</style>