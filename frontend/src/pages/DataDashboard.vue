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
import { useDashboardStore } from '@/stores/dashboard'
import { useDashboardCharts } from '@/composables/useDashboardCharts'
import { useDashboardKpiCards } from '@/composables/useDashboardKpiCards'
import { useDashboardRealtimeSync } from '@/composables/useDashboardRealtimeSync'
import { useDashboardDisplay } from '@/composables/useDashboardDisplay'

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

// ── KPI card definitions (extracted to composable — Phase 7 D round 2) ──
const kpiCards = useDashboardKpiCards(store)

// ── Chart options (extracted to composable — M15) ──
const { darkPieOption, treemapOption, trendOption, radarOption } = useDashboardCharts(store)

// ── Display maps + pipeline defaults + time formatter (Phase 7 D round 9) ──
const { pipelineStages, statusColor, eventIcon, eventSeverityColor, formatTime } = useDashboardDisplay(store)

// ── Realtime sync (SSE + periodic refresh + clock) — Phase 7 D round 3 ──
useDashboardRealtimeSync(
  store,
  '/api/v1/dashboard/realtime',
  '/api/v1/dashboard/realtime-poll',
)
</script>

<template>
  <DashboardLayout
    title="StarMap 数据大屏"
    subtitle="实时数据监控与可视化"
  >
    <div class="dashboard-grid">
      <!-- ══════════════ TOP ROW: 6 KPI CARDS ══════════════ -->
      <div class="kpi-row">
        <router-link
          v-for="card in kpiCards"
          :key="card.label"
          :to="card.route"
          class="kpi-card"
          :style="{
            '--kpi-color': card.color,
            '--kpi-glow': card.glow,
          }"
        >
          <div class="kpi-glow-bg" />
          <div class="kpi-icon">
            {{ card.icon }}
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
              :option="darkPieOption"
              autoresize
              :style="{ height: '100%' }"
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
              :option="treemapOption"
              autoresize
              :style="{ height: '100%' }"
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
              :option="trendOption"
              autoresize
              :style="{ height: '100%' }"
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
              :class="{ connected: store.sseConnected }"
            >
              <span class="sse-dot" />
              {{ store.sseConnected ? 'SSE 已连接' : '轮询中' }}
            </span>
          </div>
          <div class="event-stream">
            <TransitionGroup name="event-slide">
              <div
                v-for="evt in store.realtimeEvents.slice(0, 20)"
                :key="evt.id"
                class="event-item"
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
              <div class="event-empty-pulse" />
              <span>等待实时事件...</span>
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
                <span class="stage-label">{{ stage.stage }}</span>
              </div>
              <div
                v-if="idx < pipelineStages.length - 1"
                class="stage-connector"
              >
                <span class="connector-line" />
                <span class="connector-arrow">›</span>
              </div>
            </div>
          </div>
          <div class="pipeline-stats">
            <div class="stat-item">
              <span class="stat-value">{{ store.overview?.today_crawl_volume?.toLocaleString() ?? '--' }}</span>
              <span class="stat-label">今日采集</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ store.overview?.today_matches?.toLocaleString() ?? '--' }}</span>
              <span class="stat-label">今日匹配</span>
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
              :option="radarOption"
              autoresize
              :style="{ height: '100%' }"
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
  gap: 14px;
  height: calc(100vh - 72px);
  min-height: 700px;
}

/* ── KPI Row ── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  flex-shrink: 0;
}

.kpi-card {
  position: relative;
  background: var(--dash-surface);
  border: 1px solid var(--dash-accent-10);
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  overflow: hidden;
  transition: all 0.3s ease;
  cursor: pointer;
  text-decoration: none;
  color: inherit;
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
  gap: 14px;
  flex: 1;
  min-height: 0;
}

/* ── Bottom Row ── */
.bottom-row {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr 1fr;
  gap: 14px;
  flex: 1;
  min-height: 0;
}

/* ═══════════════════════════════════════════
   Panel (shared card style)
   ═══════════════════════════════════════════ */
.panel {
  background: var(--dash-surface);
  border: 1px solid var(--dash-accent-10);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
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
  color: var(--dash-disconnected);
}

.sse-indicator.connected {
  color: var(--dash-connected);
}

.sse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse-dot 2s ease-in-out infinite;
}

.sse-indicator.connected .sse-dot {
  animation: pulse-dot-green 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

@keyframes pulse-dot-green {
  0%, 100% { opacity: 0.6; box-shadow: 0 0 4px color-mix(in srgb, var(--success) 30%, transparent); }
  50% { opacity: 1; box-shadow: 0 0 8px color-mix(in srgb, var(--success) 60%, transparent); }
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
  padding: 6px 0;
  border-bottom: 1px solid var(--dash-text-04);
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

.event-empty-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dash-accent-40);
  animation: pulse-ring 2s ease-in-out infinite;
}

@keyframes pulse-ring {
  0% { transform: scale(0.8); opacity: 0.6; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.8); opacity: 0.6; }
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
