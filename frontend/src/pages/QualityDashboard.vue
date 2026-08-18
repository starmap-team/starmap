<script setup lang="ts">
/**
 * 图谱质量仪表盘 — R6 曾洋涛
 * 4 指标卡（含趋势箭头）+ 信任度直方图 + 幻觉率趋势 + 数据源饼图 + 审核队列
 */
import { ElMessage } from 'element-plus'
import { RefreshRight, QuestionFilled } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useQualityStore } from '@/stores/quality'
import { useReviewStore, type ReviewEntityType } from '@/stores/review'
import { chartColors } from '@/utils/chartTheme'
import QualityTrendChart from '@/components/QualityTrendChart.vue'
import AlertList from '@/components/AlertList.vue'
import { useQualityDashboardCharts } from '@/composables/useQualityDashboardCharts'
import { useQualityActions } from '@/composables/useQualityActions'
import { useQualityDashboard } from '@/composables/useQualityDashboard'

const quality = useQualityStore()
const review = useReviewStore()
// ponytail: chartColors re-exported for template el-progress :color binding
const cc = chartColors()
const {
  kpiCardsEnhanced,
  histogramOption,
  trendChartOption,
  sourceChartOption,
} = useQualityDashboardCharts(quality)

// Page-level orchestration (activeTab + auto-refresh + initial fetch — D round 11)
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

// ponytail: 原模板内联 `quality.fetchQuality; lastRefresh=...` 未 await，
// 请求失败也显示"已刷新"；改为 await 后成功才置位，失败提示
async function handleRefresh() {
  try {
    await quality.fetchQuality()
    lastRefresh.value = new Date().toLocaleTimeString()
  } catch (err: unknown) {
    ElMessage.error('刷新失败：' + (err instanceof Error ? err.message : '未知错误'))
  }
}

// ── 待审核队列操作（2026-08-13 对齐 admin 内容审核 review_service 状态机）──
// 修复前走旧 /admin/audit/{id}/approve（ReviewQueue 死代码）；audit_queue 现返回
// position/skill 的 entity_type+entity_id，审批后刷新队列与 KPI
async function handleQueueApprove(row: { entity_type?: string; entity_id?: string }) {
  if (!row.entity_type || !row.entity_id) return
  try {
    await review.approve(row.entity_type as ReviewEntityType, row.entity_id)
    ElMessage.success('已通过审核')
    await quality.fetchQuality()
  } catch {
    ElMessage.error('审批失败')
  }
}

async function handleQueueReject(row: { entity_type?: string; entity_id?: string }) {
  if (!row.entity_type || !row.entity_id) return
  try {
    await review.reject(row.entity_type as ReviewEntityType, row.entity_id, '质量仪表盘拒绝')
    ElMessage.success('已拒绝')
    await quality.fetchQuality()
  } catch {
    ElMessage.error('拒绝失败')
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
          <!-- 新手友好引导（沿 ui-ux-pro-max：data-dense dashboard，新手需一句话入口）-->
          <el-alert
            class="kpi-help-alert"
            type="info"
            :closable="false"
            show-icon
          >
            <strong>什么是图谱健康度？</strong>
            4 张卡片展示 StarMap 图谱的整体质量：节点规模（总节点/周新增）、数据可信度（平均信任度）、抽取可靠性（幻觉率）、人工监督（待审核）。每张卡片 hover <strong>口径</strong> 行可看"这个数怎么算 + 数据源"。两个菜单（/quality vs /evolution）的口径差异在「平均信任度」卡 caption 已说明。
          </el-alert>
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
            <el-tooltip
              placement="top-start"
              :show-after="300"
              popper-class="kpi-tooltip"
            >
              <template #content>
                <div class="kpi-tooltip-content">
                  <pre>{{ card.tooltip }}</pre>
                </div>
              </template>
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
                    <span>{{ card.label }}</span>
                    <!-- 新手友好：问号图标引导 hover tooltip -->
                    <el-icon class="kpi-help-icon"><QuestionFilled /></el-icon>
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
                  <!--: 口径拆解行（沿 KPI breakdown）-->
                  <div class="kpi-caption" data-testid="kpi-caption">
                    {{ card.caption }}
                  </div>
                </div>
              </div>
            </el-tooltip>
          </el-card>
        </el-col>
      </el-row>

      <!-- 数据诚实化：抽取质量基线。无 golden-set 基线时显“未评估”说明，
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
          >
            <template #header>
              <div class="review-queue-header">
                <span>待审核队列</span>
                <span
                  v-if="quality.metrics?.pending_review"
                  class="review-queue-total"
                >共 {{ quality.metrics.pending_review }} 条，显示最近 20 条</span>
                <el-button
                  size="small"
                  type="primary"
                  plain
                  @click="$router.push('/admin')"
                >
                  前往内容审核
                </el-button>
              </div>
            </template>
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
              <!--: 审核状态徽标三色（沿 audit 模式）-->
              <el-table-column
                prop="review_status"
                label="状态"
                width="100"
                align="center"
              >
                <template #default="{ row }">
                  <el-tag
                    v-if="row.review_status"
                    :type="row.review_status === 'approved' ? 'success' : row.review_status === 'rejected' ? 'danger' : 'warning'"
                    size="small"
                    effect="light"
                    data-testid="review-status-badge"
                  >
                    {{ row.review_status === 'approved' ? '已通过' : row.review_status === 'rejected' ? '已拒绝' : '待审核' }}
                  </el-tag>
                  <el-tag
                    v-else
                    type="warning"
                    size="small"
                    effect="light"
                    data-testid="review-status-badge"
                  >
                    待审核
                  </el-tag>
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
                    :disabled="row.review_status === 'approved' || row.review_status === 'rejected'"
                    @click="handleQueueApprove(row)"
                  >
                    通过
                  </el-button>
                  <el-button
                    size="small"
                    type="danger"
                    plain
                    :disabled="row.review_status === 'approved' || row.review_status === 'rejected'"
                    @click="handleQueueReject(row)"
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
.kpi-caption {
  font-size: 11px;
  color: var(--muted-foreground);
  opacity: 0.75;
  margin-top: var(--space-1);
  line-height: 1.4;
  font-style: italic;
}
.kpi-card {
 /* ui-ux-pro-max: 4 卡片高度统一（消除 147/163/167/224 高度差）*/
  min-height: 180px;
}
/* 2026-08-14: 待审核队列 header — 总数说明 + 跳转管理后台按钮（联动 admin 内容审核）*/
.review-queue-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.review-queue-total {
  flex: 1;
  font-size: 12px;
  color: var(--muted-foreground);
}
.kpi-help-icon {
 /* 新手友好：问号图标——hover 触发 tooltip 展示完整说明 */
  margin-left: 4px;
  font-size: 12px;
  color: var(--muted-foreground);
  cursor: help;
  opacity: 0.6;
  transition: opacity 150ms ease;
}
.kpi-help-icon:hover {
  opacity: 1;
}
.kpi-label {
  display: flex;
  align-items: center;
}
.kpi-tooltip-content pre {
 /* tooltip 内容保留换行（沿 ui-ux-pro-max：新手友好 + 易读）*/
  margin: 0;
  padding: 0;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  max-width: 280px;
}
.kpi-help-alert {
 /* 顶部新手引导块（沿 ui-ux-pro-max 数据密集 + 新手友好）*/
  margin-top: var(--space-2);
  font-size: 13px;
  line-height: 1.6;
}
.kpi-help-alert :deep(.el-alert__content) {
  padding-left: var(--space-2);
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