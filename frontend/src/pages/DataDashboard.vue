<script setup lang="ts">
/**
 * 数据大屏 — StarMap 实时数据大盘
 * 全屏暗色主题，6 KPI 卡片 + 数据来源饼图 + 技能域 Treemap + 质量趋势
 * + 实时事件流 + 流水线状态 + 新兴技能雷达
 */
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
import DashboardLayout from '@/layouts/DashboardLayout.vue'
import CountUpNumber from '@/components/CountUpNumber.vue'
import EmptyState from '@/components/EmptyState.vue'
import DashboardSkeleton from '@/components/DashboardSkeleton.vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useDataDashboard } from '@/composables/useDataDashboard'
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
  pipelineStages, statusColor, eventIcon, eventSeverityColor, eventTypeColor, formatTime, stageIcon,
  clockTick, connectionState,
} = useDataDashboard(store, `${sseBase}/dashboard/realtime`, `${sseBase}/dashboard/realtime-poll`)
</script>

<template>
  <DashboardLayout
    title="StarMap 数据大屏"
    subtitle="实时数据监控与可视化"
    :clock-tick="clockTick"
    :stale="store.overview?.stale ?? false"
    :stale-since="store.overview?.stale_since ?? ''"
  >
    <DashboardSkeleton v-if="store.loading && !store.overview" />
    <div
      v-else
      class="dashboard-grid"
    >
      <!-- ══════════════ TOP ROW: 6 KPI CARDS ══════════════ -->
      <div class="kpi-row">
        <router-link
          v-for="card in kpiCards"
          :key="card.label"
          :to="card.route"
          class="kpi-card"
          :aria-label="`${card.label}: ${card.target}${card.suffix || ''}`"
          :style="{
            '--kpi-color': card.color,
            '--kpi-glow': card.glow,
          }"
        >
          <div class="kpi-glow-bg" />
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
          <div class="kpi-border-bottom" />
        </router-link>
      </div>

      <!-- ══════════════ MIDDLE ROW ══════════════ -->
      <div class="middle-row">
        <!-- Left: Data source distribution pie -->
        <div class="panel middle-left">
          <div class="panel-header">
            <span class="panel-title">数据来源分布</span>
            <span class="panel-badge">PIE</span>
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

        <!-- Center: Skill domain treemap -->
        <div class="panel middle-center">
          <div class="panel-header">
            <span class="panel-title">技能域分布</span>
            <span class="panel-badge">TREEMAP</span>
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
            <span class="panel-badge">7D</span>
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
              <template v-else-if="connectionState === 'connected'">SSE 已连接</template>
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
                  <span class="event-detail">{{ evt.detail }}</span>
                </div>
                <span
                  class="event-time"
                  :style="{ color: eventSeverityColor[evt.severity || 'info'] }"
                >{{ formatTime(evt.timestamp) }}</span>
              </div>
            </TransitionGroup>
            <div
              v-if="!store.realtimeEvents.length"
              class="event-empty"
            >
              <div
                class="event-typing-dots"
                aria-hidden="true"
              >
                <span class="event-typing-dot" />
                <span class="event-typing-dot" />
                <span class="event-typing-dot" />
              </div>
              <span class="event-empty-label">等待实时事件...</span>
            </div>
          </div>
        </div>

        <!-- Bottom Center: Pipeline status mini timeline -->
        <div class="panel bottom-center">
          <div class="panel-header">
            <span class="panel-title">流水线状态</span>
            <span class="panel-badge">PIPELINE</span>
          </div>
          <div class="pipeline-mini">
            <template v-if="pipelineStages.length">
              <div
                v-for="(stage, idx) in pipelineStages"
                :key="stage.stage"
                class="pipeline-stage"
              >
                <div
                  class="stage-node"
                  :style="{ borderColor: statusColor[stage.status] }"
                >
                  <div
                    class="stage-fill"
                    :style="{
                      background: statusColor[stage.status],
                      height: stage.progress + '%',
                    }"
                  />
                  <span
                    class="stage-icon"
                    :class="`stage-icon-${stage.status}`"
                  >{{ stageIcon(stage.status) }}</span>
                  <span class="stage-label">{{ stage.stage }}</span>
                </div>
                <div
                  v-if="idx < pipelineStages.length - 1"
                  class="stage-connector"
                  :class="`stage-connector-${pipelineStages[idx].status}`"
                >
                  <span class="connector-line" />
                  <span class="connector-arrow">›</span>
                </div>
              </div>
            </template>
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
              <span class="stat-value">{{ store.overview?.pipeline_status ?? '--' }}</span>
              <span class="stat-label">状态</span>
            </div>
          </div>
        </div>

        <!-- Bottom Right: Emerging skills radar -->
        <div class="panel bottom-right">
          <div class="panel-header">
            <span class="panel-title">新兴技能雷达</span>
            <span class="panel-badge">RADAR</span>
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
    </div>
  </DashboardLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════
   Dashboard Grid Layout
   ═══════════════════════════════════════════ */
.dashboard-grid {
  display: flex;
  flex-direction: column;
  gap: var(--gap-md);
  height: calc(100vh - 72px);
  min-height: 700px;
}

/* ── KPI Row ── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--gap-md);
  flex-shrink: 0;
}

.kpi-card {
  position: relative;
  background: var(--dash-surface);
  border: 1px solid var(--dash-accent-10);
  border-radius: var(--radius-lg, 8px);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: var(--gap-md);
  overflow: hidden;
  transition: all 0.3s ease;
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  box-shadow: var(--shadow-subtle);
}

.kpi-card:hover {
  border-color: var(--kpi-color);
  box-shadow: 0 0 20px var(--kpi-glow), inset 0 0 20px var(--kpi-glow);
  transform: translateY(-2px);
}

.kpi-glow-bg {
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, var(--kpi-glow) 0%, transparent 70%);
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}

.kpi-card:hover .kpi-glow-bg {
  opacity: 0.3;
}

.kpi-border-bottom {
  position: absolute;
  bottom: 0;
  left: 10%;
  width: 80%;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--kpi-color), transparent);
  opacity: 0.4;
}

.kpi-icon {
  font-size: 24px;
  color: var(--kpi-color);
  filter: drop-shadow(0 0 6px var(--kpi-glow));
  flex-shrink: 0;
}

.kpi-body {
  flex: 1;
  min-width: 0;
}

.kpi-label {
  font-size: 11px;
  color: var(--dash-text-50);
  font-weight: 500;
  margin-bottom: 2px;
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--kpi-color);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  text-shadow: 0 0 12px var(--kpi-glow);
  line-height: 1.1;
}

/* ── Middle Row ── */
.middle-row {
  display: grid;
  grid-template-columns: 1fr 1.5fr 1fr;
  gap: var(--gap-md);
  flex: 1;
  min-height: 0;
}

/* ── Bottom Row ── */
.bottom-row {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr 1fr;
  gap: var(--gap-md);
  flex: 1;
  min-height: 0;
}

/* ═══════════════════════════════════════════
   Panel (shared card style)
   ═══════════════════════════════════════════ */
.panel {
  background: var(--dash-surface);
  border: 1px solid var(--dash-accent-10);
  border-radius: var(--radius-lg, 8px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--shadow-subtle);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--dash-accent-8);
  flex-shrink: 0;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--dash-text-85);
  letter-spacing: 0.02em;
}

.panel-badge {
  font-size: 9px;
  font-weight: 600;
  color: var(--chart-1);
  background: var(--dash-accent-8);
  padding: 2px 6px;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.chart-container {
  flex: 1;
  min-height: 0;
  padding: 4px;
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

/* 4-state connection colors */
.sse-indicator.connecting {
  color: var(--el-color-info, #909399);
}

.sse-indicator.connected {
  color: var(--el-color-success, #67c23a);
}

.sse-indicator.polling {
  color: var(--el-color-warning, #e6a23c);
}

.sse-indicator.disconnected {
  color: var(--el-color-danger, #f56c6c);
}

.sse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

/* connecting: pulsing dot */
.sse-indicator.connecting .sse-dot {
  animation: pulse-dot 1.5s ease-in-out infinite;
}

/* connected: solid dot */
.sse-indicator.connected .sse-dot {
  animation: none;
  opacity: 1;
}

/* polling: slower pulsing dot */
.sse-indicator.polling .sse-dot {
  animation: pulse-dot-slow 3s ease-in-out infinite;
}

/* disconnected: dot off */
.sse-indicator.disconnected .sse-dot {
  animation: none;
  opacity: 0.3;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

@keyframes pulse-dot-slow {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.event-stream {
  flex: 1;
  overflow-y: auto;
  padding: 6px 10px;
  min-height: 0;
}

.event-stream::-webkit-scrollbar {
  width: 4px;
}
.event-stream::-webkit-scrollbar-track {
  background: transparent;
}
.event-stream::-webkit-scrollbar-thumb {
  background: var(--dash-accent-15);
  border-radius: 2px;
}

.event-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--dash-text-04);
  border-left: 2px solid var(--chart-1);
  animation: event-in 0.3s ease-out;
}

@keyframes event-in {
  from {
    opacity: 0;
    transform: translateX(-12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
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
  color: var(--dash-text-80);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-detail {
  font-size: 10px;
  color: var(--dash-text-40);
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

.event-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 10px;
  color: var(--dash-text-30);
  font-size: 12px;
}

.event-typing-dots {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 10px;
}

.event-typing-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--dash-accent-40);
  animation: dash-typing-pulse 1.2s ease-in-out infinite;
}

.event-typing-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.event-typing-dot:nth-child(3) {
  animation-delay: 0.4s;
}

.event-empty-label {
  letter-spacing: 0.02em;
}

/* TransitionGroup for events */
.event-slide-enter-active {
  transition: all 0.3s ease-out;
}
.event-slide-leave-active {
  transition: all 0.2s ease-in;
}
.event-slide-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}
.event-slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

/* ═══════════════════════════════════════════
   Pipeline Mini Timeline
   ═══════════════════════════════════════════ */
.pipeline-mini {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 16px 12px 10px;
  flex-shrink: 0;
}

.pipeline-stage {
  display: flex;
  align-items: center;
  gap: 0;
}

.stage-node {
  width: 52px;
  height: 52px;
  border: 2px solid var(--dash-accent-20);
  border-radius: 50%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  transition: border-color 0.3s ease;
}

.stage-fill {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  opacity: 0.25;
  transition: height 0.5s ease;
}

.stage-icon {
  position: relative;
  z-index: 2;
  font-size: 14px;
  line-height: 1;
  color: var(--dash-text-85);
  text-shadow: 0 0 8px currentColor;
}

.stage-icon-running {
  animation: pulse-dot 1.5s ease-in-out infinite;
}

.stage-icon-completed {
  color: var(--el-color-success, #67c23a);
}

.stage-icon-failed {
  color: var(--el-color-danger, #f56c6c);
}

.stage-icon-waiting {
  color: var(--dash-text-40);
}

.stage-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--dash-text-80);
  position: relative;
  z-index: 1;
}

.stage-connector {
  display: flex;
  align-items: center;
  padding: 0 4px;
}

.connector-line {
  display: block;
  width: 16px;
  height: 2px;
  background: var(--dash-accent-15);
  border-radius: 1px;
}

.connector-arrow {
  font-size: 14px;
  font-weight: 700;
  color: var(--dash-accent-20);
  line-height: 1;
}

.stage-connector-completed .connector-line,
.stage-connector-running .connector-line {
  background: var(--el-color-success, #67c23a);
  background-image: linear-gradient(90deg, transparent 25%, currentColor 25%, currentColor 50%, transparent 50%, transparent 75%, currentColor 75%);
  background-size: 8px 100%;
  animation: connector-flow 1s linear infinite;
}

.stage-connector-running .connector-line {
  color: var(--el-color-primary, #409eff);
  background-color: var(--el-color-primary, #409eff);
}

.stage-connector-completed .connector-arrow {
  color: var(--el-color-success, #67c23a);
}

.stage-connector-running .connector-arrow {
  color: var(--el-color-primary, #409eff);
}

@keyframes connector-flow {
  from { background-position: 0 0; }
  to { background-position: 8px 0; }
}

.pipeline-stats {
  display: flex;
  justify-content: space-around;
  padding: 8px 12px;
  border-top: 1px solid var(--dash-accent-6);
  flex: 1;
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
  color: var(--dash-text-85);
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 9px;
  color: var(--dash-text-40);
}

/* ═══════════════════════════════════════════
   Responsive: 1440px
   ═══════════════════════════════════════════ */
@media (max-width: 1600px) {
  .kpi-row {
    grid-template-columns: repeat(3, 1fr);
  }
  .middle-row {
    grid-template-columns: 1fr 1fr;
  }
  .middle-right {
    grid-column: 1 / -1;
  }
  .bottom-row {
    grid-template-columns: 1fr 1fr;
  }
  .bottom-right {
    grid-column: 1 / -1;
  }
}

@media (max-width: 1024px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .middle-row,
  .bottom-row {
    grid-template-columns: 1fr;
  }
  .middle-right,
  .bottom-right {
    grid-column: auto;
  }
  .dashboard-grid {
    height: auto;
  }
  .middle-row,
  .bottom-row {
    flex: none;
  }
  .panel {
    min-height: 260px;
  }
}
</style>
