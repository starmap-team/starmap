<script setup lang="ts">
/**
 * 数据大屏 — StarMap 实时数据大盘
 * 2026-08-13 (deep-interview): 从沉浸式大屏壳回归 MainLayout 普通页面风格。
 * 保留 8 KPI + 6 面板（来源饼图 / 行业 Treemap / 质量趋势 / 实时事件流 /
 * 流水线状态 / 新兴技能雷达），但采用项目统一的卡片/令牌体系，随亮暗主题自适应。
 */
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import {
  PieChart,
  TreemapChart,
  LineChart,
  RadarChart,
} from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  RadarComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import MainLayout from '@/layouts/MainLayout.vue'
import CountUpNumber from '@/components/CountUpNumber.vue'
import EmptyState from '@/components/EmptyState.vue'
import DashboardSkeleton from '@/components/DashboardSkeleton.vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useDataDashboard } from '@/composables/useDataDashboard'
import { STAGE_LABELS } from '@/stores/pipelineConfig'
import { API_BASE } from '@/config/apiBase'

use([
  PieChart,
  TreemapChart,
  LineChart,
  RadarChart,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  RadarComponent,
  VisualMapComponent,
  CanvasRenderer,
])

const store = useDashboardStore()

// ── Unified dashboard composable (merged 4 single-caller files → 1) ──
const sseBase = API_BASE
const {
  kpiCards,
  darkPieOption, treemapOption, trendOption, radarOption,
  pipelineStages, statusColor, eventIcon, eventSeverityColor, eventTypeColor,
  formatTime, stageIcon, pipelineStatusLabel,
  connectionState,
} = useDataDashboard(store, `${sseBase}/dashboard/realtime`, `${sseBase}/dashboard/realtime-poll`)

// 阶段中文名（对齐 PipelineStageCard 的 STAGE_LABELS，契约真相源）
function stageLabel(name: string): string {
  return STAGE_LABELS[name] || name
}

// 阶段进度：后端 progress 为 0-1 小数，渲染需 ×100（deep-interview A2）
function stageProgressPct(progress: number): number {
  if (progress === null || progress === undefined) return 0
  return Math.round(progress * 100)
}

// 数据新鲜度徽标（deep-interview R6：保留徽标，时钟随壳移除）
const isStale = computed(() => store.overview?.stale ?? false)
const staleLabel = computed(() => {
  const since = store.overview?.stale_since
  if (!since) return '数据过期'
  const mins = Math.max(1, Math.round((Date.now() / 1000 - since) / 60))
  return `数据过期（${mins} 分钟前）`
})
</script>

<template>
  <MainLayout>
    <div class="dashboard-page animate-fade-in">
      <!-- ══════════════ 页面头（对齐 QualityDashboard page-header 模式） ══════════════ -->
      <div class="page-header">
        <div>
          <h2>数据大屏</h2>
          <p class="page-desc">
            实时数据监控与可视化：图谱规模、数据来源、质量趋势与流水线状态
          </p>
        </div>
        <div class="header-actions">
          <span
            class="freshness-badge"
            :class="isStale ? 'stale' : 'fresh'"
            :title="isStale ? staleLabel : '数据每 30 秒自动刷新，SSE 实时推送'"
          >
            <span class="freshness-dot" />
            {{ isStale ? staleLabel : '数据实时' }}
          </span>
        </div>
      </div>

      <DashboardSkeleton v-if="store.loading && !store.overview" />
      <template v-else>
        <!-- ══════════════ TOP ROW: 8 KPI CARDS ══════════════ -->
        <div class="kpi-row">
          <router-link
            v-for="card in kpiCards"
            :key="card.label"
            :to="card.route"
            class="kpi-card"
            :aria-label="`${card.label}: ${card.target}${card.suffix || ''}`"
            :style="{ '--kpi-color': card.color }"
          >
            <div class="kpi-icon">
              <el-icon :size="20">
                <component :is="card.icon" />
              </el-icon>
            </div>
            <div class="kpi-body">
              <div class="kpi-label">
                {{ card.label }}
              </div>
              <div class="kpi-value">
                <CountUpNumber
                  :target="card.target"
                  :suffix="card.suffix"
                  :decimals="card.decimals"
                  :duration="1500"
                />
              </div>
            </div>
          </router-link>
        </div>

        <!-- ══════════════ MIDDLE ROW ══════════════ -->
        <div class="middle-row">
          <!-- Left: Data source distribution pie -->
          <div class="panel middle-left">
            <div class="panel-header">
              <span class="panel-title">数据来源分布</span>
              <span class="panel-badge">饼图</span>
            </div>
            <div class="chart-container">
              <VChart
                v-if="darkPieOption"
                :option="darkPieOption"
                autoresize
                :style="{ height: '100%' }"
              />
              <EmptyState
                v-else
                title="暂无数据"
                description="数据加载中或暂无记录"
                icon="📊"
              />
            </div>
          </div>

          <!-- Center: Industry domain treemap（deep-interview B1：原"技能域分布"实际统计行业） -->
          <div class="panel middle-center">
            <div class="panel-header">
              <span class="panel-title">行业分布</span>
              <span class="panel-badge">树图</span>
            </div>
            <div class="chart-container">
              <VChart
                v-if="treemapOption"
                :option="treemapOption"
                autoresize
                :style="{ height: '100%' }"
              />
              <EmptyState
                v-else
                title="暂无数据"
                description="数据加载中或暂无记录"
                icon="🧭"
              />
            </div>
          </div>

          <!-- Right: Quality trend dual-axis -->
          <div class="panel middle-right">
            <div class="panel-header">
              <span class="panel-title">质量趋势</span>
              <span class="panel-badge">近 7 天</span>
            </div>
            <div class="chart-container">
              <VChart
                v-if="trendOption"
                :option="trendOption"
                autoresize
                :style="{ height: '100%' }"
              />
              <EmptyState
                v-else
                title="暂无数据"
                description="数据加载中或暂无记录"
                icon="📈"
              />
            </div>
          </div>
        </div>

        <!-- ══════════════ BOTTOM ROW ══════════════ -->
        <div class="bottom-row">
          <!-- Bottom Left: Real-time event stream -->
          <div class="panel bottom-left">
            <div class="panel-header">
              <span class="panel-title">实时事件流</span>
              <span
                class="sse-indicator"
                :class="connectionState"
              >
                <span class="sse-dot" />
                <template v-if="connectionState === 'connecting'">连接中...</template>
                <template v-else-if="connectionState === 'connected'">实时连接正常</template>
                <template v-else-if="connectionState === 'polling'">轮询中</template>
                <template v-else>已断开</template>
              </span>
            </div>
            <div class="event-stream">
              <TransitionGroup name="event-slide">
                <div
                  v-for="evt in store.realtimeEvents.slice(0, 20)"
                  :key="evt.id"
                  class="event-item"
                  :style="{ borderLeftColor: eventTypeColor[evt.type] || 'var(--chart-1)' }"
                >
                  <span class="event-icon">{{ eventIcon[evt.type] || '📡' }}</span>
                  <div class="event-body">
                    <span class="event-title">{{ evt.title }}</span>
                    <span
                      v-if="evt.detail"
                      class="event-detail"
                    >{{ evt.detail }}</span>
                  </div>
                  <span
                    class="event-time"
                    :style="{ color: eventSeverityColor[evt.severity || 'info'] }"
                  >{{ formatTime(evt.timestamp) }}</span>
                </div>
              </TransitionGroup>
              <!-- deep-interview A4：诚实空态 — SSE 事件仅在流水线运行时产生 -->
              <div
                v-if="!store.realtimeEvents.length"
                class="event-empty"
              >
                <span class="event-empty-icon">📡</span>
                <span class="event-empty-label">暂无近期事件</span>
                <span class="event-empty-hint">流水线运行时将实时展示事件</span>
              </div>
            </div>
          </div>

          <!-- Bottom Center: Pipeline status mini timeline -->
          <div class="panel bottom-center">
            <div class="panel-header">
              <span class="panel-title">流水线状态</span>
              <span class="panel-badge">最近运行</span>
            </div>
            <div class="pipeline-mini">
              <div
                v-if="pipelineStages.length"
                class="pipeline-track"
              >
                <div
                  v-for="(stage, idx) in pipelineStages"
                  :key="stage.name"
                  class="pipeline-stage"
                >
                  <div class="stage-column">
                    <div
                      class="stage-node"
                      :class="`stage-node-${stage.status}`"
                      :style="{ borderColor: statusColor[stage.status] }"
                    >
                      <div
                        class="stage-fill"
                        :style="{
                          background: statusColor[stage.status],
                          height: stageProgressPct(stage.progress) + '%',
                        }"
                      />
                      <span
                        class="stage-icon"
                        :class="`stage-icon-${stage.status}`"
                      >{{ stageIcon(stage.status) }}</span>
                    </div>
                    <!-- deep-interview D2：标签移至节点下方（原塞在 overflow:hidden 圆内被裁剪） -->
                    <span class="stage-label">{{ stageLabel(stage.name) }}</span>
                  </div>
                  <div
                    v-if="idx < pipelineStages.length - 1"
                    class="stage-connector"
                    :class="`stage-connector-${stage.status}`"
                  >
                    <span class="connector-line" />
                    <span class="connector-arrow">›</span>
                  </div>
                </div>
              </div>
              <!-- ponytail: 无流水线数据时显示空态而非假阶段 -->
              <div
                v-else
                class="pipeline-empty"
              >
                暂无流水线运行数据
              </div>
            </div>
            <div class="pipeline-stats">
              <div class="stat-item">
                <span class="stat-value">{{ store.overview?.today_extractions?.toLocaleString() ?? '--' }}</span>
                <span class="stat-label">今日抽取</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ store.overview?.data_volume?.toLocaleString() ?? '--' }}</span>
                <span class="stat-label">数据总量</span>
              </div>
              <div class="stat-item">
                <!-- deep-interview A6：pipeline_status 汉化（原显示原始英文 completed） -->
                <span
                  class="stat-value"
                  :class="`status-${store.overview?.pipeline_status ?? 'idle'}`"
                >{{ pipelineStatusLabel(store.overview?.pipeline_status ?? '') }}</span>
                <span class="stat-label">状态</span>
              </div>
            </div>
          </div>

          <!-- Bottom Right: Emerging skills radar -->
          <div class="panel bottom-right">
            <div class="panel-header">
              <span class="panel-title">新兴技能雷达</span>
              <span class="panel-badge">雷达图</span>
            </div>
            <div class="chart-container">
              <VChart
                v-if="radarOption"
                :option="radarOption"
                autoresize
                :style="{ height: '100%' }"
              />
              <EmptyState
                v-else
                title="暂无数据"
                description="数据加载中或暂无记录"
                icon="🛰️"
              />
            </div>
          </div>
        </div>

        <!-- Phase 3 创新性可视化：多源异构数据清洗 + 幻觉防控 + 动态演化 -->
        <div class="innovation-section">
          <h3 class="section-title">创新性技术方案</h3>
          <div class="innovation-grid">
            <!-- 多源异构数据清洗验证 -->
            <div class="panel innovation-card">
              <div class="panel-header">
                <span class="panel-title">数据清洗验证</span>
                <span class="panel-badge">多源异构</span>
              </div>
              <div class="innovation-content">
                <div class="innovation-metric">
                  <span class="metric-value">{{ store.overview?.hallucination_rate ? ((1 - store.overview.hallucination_rate) * 100).toFixed(1) : '0.0' }}%</span>
                  <span class="metric-label">Anti-Hallucination 通过率</span>
                </div>
                <div class="innovation-metric">
                  <span class="metric-value">{{ store.overview?.trust_score ? (store.overview.trust_score * 100).toFixed(1) : '0.0' }}%</span>
                  <span class="metric-label">跨源验证信任度</span>
                </div>
                <div class="innovation-desc">
                  SimHash去重 + 多源交叉验证 + 幻觉防控：解决 JD 数据"时滞"、"噪音"、"抄袭"问题
                </div>
              </div>
            </div>
            <!-- 动态演化感知 -->
            <div class="panel innovation-card">
              <div class="panel-header">
                <span class="panel-title">动态演化感知</span>
                <span class="panel-badge">自进化</span>
              </div>
              <div class="innovation-content">
                <div class="innovation-metric">
                  <span class="metric-value">{{ store.overview?.total_domains ?? 0 }}</span>
                  <span class="metric-label">行业域数</span>
                </div>
                <div class="innovation-metric">
                  <span class="metric-value">{{ store.emergingSkills?.length ?? 0 }}</span>
                  <span class="metric-label">涌现技能数</span>
                </div>
                <div class="innovation-desc">
                  Z-score涌现检测 + CII能力通胀指数 + 新岗位发现：从"静态画像"向"动态感知"跨越
                </div>
              </div>
            </div>
            <!-- 技术可迁移性 -->
            <div class="panel innovation-card">
              <div class="panel-header">
                <span class="panel-title">技术可迁移性</span>
                <span class="panel-badge">标准化</span>
              </div>
              <div class="innovation-content">
                <div class="innovation-metric">
                  <span class="metric-value">{{ store.overview?.total_skills ?? 0 }}</span>
                  <span class="metric-label">技能图谱规模</span>
                </div>
                <div class="innovation-metric">
                  <span class="metric-value">OpenAPI</span>
                  <span class="metric-label">API 标准化</span>
                </div>
                <div class="innovation-desc">
                  标准化API + Docker部署 + JSON Schema：可迁移至更多新一代信息技术领域岗位
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </MainLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════
   2026-08-13 (deep-interview C4): 回归普通页面风格 —
   弃用 --dash-* 沉浸式令牌,改用项目统一 --card/--border/--space 体系,
   亮暗主题自动适配
   ═══════════════════════════════════════════ */
.dashboard-page {
  padding: var(--space-4);
  max-width: var(--content-max-width, 1600px);
  margin: 0 auto;
}

/* ── Page header（对齐 QualityDashboard 模式） ── */
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
}

/* ── 新鲜度徽标（deep-interview R6） ── */
.freshness-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  font-weight: 500;
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  border: 1px solid transparent;
  white-space: nowrap;
}

.freshness-badge.fresh {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 10%, transparent);
  border-color: color-mix(in srgb, var(--success) 25%, transparent);
}

.freshness-badge.stale {
  color: var(--warning);
  background: color-mix(in srgb, var(--warning) 10%, transparent);
  border-color: color-mix(in srgb, var(--warning) 25%, transparent);
}

.freshness-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.freshness-badge.fresh .freshness-dot {
  animation: freshness-pulse 2s ease-in-out infinite;
}

@keyframes freshness-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ── KPI Row（deep-interview C3：8 卡 4 列 ×2 行，消除孤儿行） ── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--gap-md);
  margin-bottom: var(--gap-md);
}

.kpi-card {
  position: relative;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg, 8px);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: var(--gap-md);
  overflow: hidden;
  transition: var(--transition-fast);
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  box-shadow: var(--shadow-subtle);
}

.kpi-card:hover {
  border-color: color-mix(in srgb, var(--kpi-color) 50%, var(--border));
  box-shadow: var(--shadow-medium);
  transform: translateY(-2px);
}

.kpi-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-lg, 8px);
  background: color-mix(in srgb, var(--kpi-color) 10%, transparent);
  color: var(--kpi-color);
  flex-shrink: 0;
}

.kpi-body {
  flex: 1;
  min-width: 0;
}

.kpi-label {
  font-size: 11px;
  color: var(--muted-foreground);
  font-weight: 500;
  margin-bottom: 2px;
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--foreground);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  line-height: 1.1;
}

/* ── Rows ── */
.middle-row {
  display: grid;
  grid-template-columns: 1fr 1.5fr 1fr;
  gap: var(--gap-md);
  margin-bottom: var(--gap-md);
}

.bottom-row {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  gap: var(--gap-md);
}

/* ═══════════════════════════════════════════
   Panel（项目标准卡片）
   ═══════════════════════════════════════════ */
.panel {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg, 8px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--shadow-subtle);
  min-height: 300px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--foreground);
  letter-spacing: 0.02em;
}

.panel-badge {
  font-size: 10px;
  font-weight: 600;
  color: var(--muted-foreground);
  background: var(--muted);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  letter-spacing: 0.02em;
}

.chart-container {
  flex: 1;
  min-height: 0;
  padding: 4px;
  height: 260px;
}

/* ═══════════════════════════════════════════
   Event Stream
   ═══════════════════════════════════════════ */
.sse-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
}

.sse-indicator.connecting { color: var(--muted-foreground); }
.sse-indicator.connected { color: var(--success); }
.sse-indicator.polling { color: var(--warning); }
.sse-indicator.disconnected { color: var(--destructive); }

.sse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.sse-indicator.connecting .sse-dot { animation: sse-pulse 1.5s ease-in-out infinite; }
.sse-indicator.connected .sse-dot { opacity: 1; }
.sse-indicator.polling .sse-dot { animation: sse-pulse 3s ease-in-out infinite; }
.sse-indicator.disconnected .sse-dot { opacity: 0.3; }

@keyframes sse-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

.event-stream {
  flex: 1;
  overflow-y: auto;
  padding: 6px 10px;
  min-height: 0;
  height: 260px;
}

.event-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 8px;
  border-bottom: 1px solid color-mix(in srgb, var(--border) 50%, transparent);
  border-left: 2px solid var(--chart-1);
  animation: event-in 0.3s ease-out;
}

@keyframes event-in {
  from { opacity: 0; transform: translateX(-12px); }
  to { opacity: 1; transform: translateX(0); }
}

.event-icon {
  font-size: 14px;
  flex-shrink: 0;
  line-height: 1.4;
}

.event-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.event-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--foreground);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-detail {
  font-size: 10px;
  color: var(--muted-foreground);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-time {
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
}

/* 诚实空态（deep-interview A4） */
.event-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 4px;
  color: var(--muted-foreground);
}

.event-empty-icon {
  font-size: 24px;
  opacity: 0.5;
  margin-bottom: 4px;
}

.event-empty-label {
  font-size: 12px;
  font-weight: 500;
}

.event-empty-hint {
  font-size: 11px;
  opacity: 0.7;
}

/* TransitionGroup for events */
.event-slide-enter-active { transition: all 0.3s ease-out; }
.event-slide-leave-active { transition: all 0.2s ease-in; }
.event-slide-enter-from { opacity: 0; transform: translateX(-20px); }
.event-slide-leave-to { opacity: 0; transform: translateX(20px); }

/* ═══════════════════════════════════════════
   Pipeline Mini Timeline
   ═══════════════════════════════════════════ */
.pipeline-mini {
  display: flex;
  align-items: flex-start;
  padding: 16px 12px 8px;
  flex-shrink: 0;
  overflow-x: auto;
}

/* 窄时 margin auto 居中，宽时横向滚动 —
   避免 justify-content:center 下左侧溢出不可达的裁切问题 */
.pipeline-track {
  display: flex;
  align-items: flex-start;
  margin: 0 auto;
  min-width: max-content;
}

.pipeline-stage {
  display: flex;
  align-items: flex-start;
}

/* deep-interview D2：节点 + 标签纵向排列，标签不再被圆裁剪 */
.stage-column {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.stage-node {
  width: 44px;
  height: 44px;
  border: 2px solid var(--border);
  border-radius: 50%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  transition: border-color 0.3s ease;
  background: var(--card);
}

.stage-fill {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  opacity: 0.2;
  transition: height 0.5s ease;
}

.stage-icon {
  position: relative;
  z-index: 2;
  font-size: 14px;
  line-height: 1;
  color: var(--foreground);
}

.stage-icon-running { animation: sse-pulse 1.5s ease-in-out infinite; color: var(--info); }
.stage-icon-completed { color: var(--success); }
.stage-icon-failed { color: var(--destructive); }
.stage-icon-waiting,
.stage-icon-pending,
.stage-icon-skipped,
.stage-icon-cancelled { color: var(--muted-foreground); }

.stage-label {
  font-size: 10px;
  font-weight: 500;
  color: var(--muted-foreground);
  white-space: nowrap;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stage-connector {
  display: flex;
  align-items: center;
  padding: 0 4px;
  height: 44px;
}

.connector-line {
  display: block;
  width: 14px;
  height: 2px;
  background: var(--border);
  border-radius: 1px;
}

.connector-arrow {
  font-size: 14px;
  font-weight: 700;
  color: var(--muted-foreground);
  line-height: 1;
}

.stage-connector-completed .connector-line { background: var(--success); }
.stage-connector-completed .connector-arrow { color: var(--success); }
.stage-connector-running .connector-line {
  background: var(--info);
  animation: connector-flow 1s linear infinite;
}
.stage-connector-running .connector-arrow { color: var(--info); }

@keyframes connector-flow {
  0% { opacity: 0.4; }
  50% { opacity: 1; }
  100% { opacity: 0.4; }
}

.pipeline-empty {
  padding: 24px;
  color: var(--muted-foreground);
  font-size: 12px;
  text-align: center;
  width: 100%;
}

.pipeline-stats {
  display: flex;
  justify-content: space-around;
  padding: 10px 12px;
  border-top: 1px solid var(--border);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-value {
  font-size: 14px;
  font-weight: 700;
  color: var(--foreground);
  font-variant-numeric: tabular-nums;
}

.stat-value.status-completed { color: var(--success); }
.stat-value.status-running { color: var(--info); }
.stat-value.status-failed { color: var(--destructive); }

.stat-label {
  font-size: 10px;
  color: var(--muted-foreground);
}

/* ═══════════════════════════════════════════
   Responsive
   ═══════════════════════════════════════════ */
@media (max-width: 1280px) {
  .kpi-row { grid-template-columns: repeat(4, 1fr); }
  .middle-row { grid-template-columns: 1fr 1fr; }
  .middle-right { grid-column: 1 / -1; }
  .bottom-row { grid-template-columns: 1fr 1fr; }
  .bottom-right { grid-column: 1 / -1; }
}

@media (max-width: 900px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
  .middle-row,
  .bottom-row { grid-template-columns: 1fr; }
  .middle-right,
  .bottom-right { grid-column: auto; }
  .page-header { flex-direction: column; }
}

/* Phase 3 创新性可视化 */
.innovation-section {
  margin-top: var(--space-6);
}
.innovation-section .section-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--foreground);
  margin-bottom: var(--space-4);
}
.innovation-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}
.innovation-card {
  border-radius: 12px;
  overflow: hidden;
}
.innovation-card .panel-header {
  padding: 12px 16px;
  background: var(--card);
  border-bottom: 1px solid var(--border);
}
.innovation-card .panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--foreground);
}
.innovation-card .panel-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--primary);
  color: white;
  margin-left: 8px;
}
.innovation-content {
  padding: 16px;
}
.innovation-metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 12px;
}
.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--foreground);
}
.metric-label {
  font-size: 12px;
  color: var(--muted-foreground);
  margin-top: 4px;
}
.innovation-desc {
  font-size: 13px;
  color: var(--muted-foreground);
  line-height: 1.5;
  padding: 8px;
  background: var(--muted);
  border-radius: 6px;
}
@media (max-width: 768px) {
  .innovation-grid { grid-template-columns: 1fr; }
}
</style>
