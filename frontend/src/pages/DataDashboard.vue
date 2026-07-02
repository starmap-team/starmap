<script setup lang="ts">
/**
 * 数据大屏 — StarMap 实时数据大盘
 * 全屏暗色主题，6 KPI 卡片 + 数据来源饼图 + 技能域 Treemap + 质量趋势
 * + 实时事件流 + 流水线状态 + 新兴技能雷达
 */
import { onMounted, onUnmounted, ref, computed, watch, nextTick } from 'vue'
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
import { useSSE } from '@/composables/useSSE'
import { chartAnimationConfig } from '@/utils/chartTheme'
import type { RealtimeEvent, EmergingSkill } from '@/stores/dashboard'

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

// ── KPI card definitions (raw targets for CountUpNumber) ──
const kpiCards = computed(() => [
  {
    label: '总节点数',
    target: store.overview?.total_nodes ?? 0,
    suffix: '',
    decimals: 0,
    icon: '⬡',
    color: '#00d4ff',
    glow: 'rgba(0, 212, 255, 0.25)',
  },
  {
    label: '总关系数',
    target: store.overview?.total_edges ?? 0,
    suffix: '',
    decimals: 0,
    icon: '◇',
    color: '#7b61ff',
    glow: 'rgba(123, 97, 255, 0.25)',
  },
  {
    label: '技能域',
    target: store.overview?.total_domains ?? 0,
    suffix: '',
    decimals: 0,
    icon: '◈',
    color: '#00ff88',
    glow: 'rgba(0, 255, 136, 0.25)',
  },
  {
    label: '岗位数',
    target: store.overview?.total_positions ?? 0,
    suffix: '',
    decimals: 0,
    icon: '◉',
    color: '#ff6b6b',
    glow: 'rgba(255, 107, 107, 0.25)',
  },
  {
    label: '技能数',
    target: store.overview?.total_skills ?? 0,
    suffix: '',
    decimals: 0,
    icon: '◆',
    color: '#ffd93d',
    glow: 'rgba(255, 217, 61, 0.25)',
  },
  {
    label: '信任评分',
    target: (store.overview?.avg_trust_score ?? 0) * 100,
    suffix: '%',
    decimals: 1,
    icon: '★',
    color: '#6bcbff',
    glow: 'rgba(107, 203, 255, 0.25)',
  },
])

// ── Data source pie chart (dark theme) ──
const darkPieOption = computed(() => {
  const data = store.sourceDistribution
  if (!data?.length) {
    return getPlaceholderPie()
  }
  const palette = ['#00d4ff', '#7b61ff', '#00ff88', '#ff6b6b', '#ffd93d', '#6bcbff', '#ff9f43', '#a29bfe']
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 15, 35, 0.9)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: '#e0e6ed', fontSize: 12 },
      formatter: '{b}: {c} 条 ({d}%)',
    },
    legend: {
      bottom: 4,
      textStyle: { color: 'rgba(224, 230, 237, 0.6)', fontSize: 10 },
      itemWidth: 10,
      itemHeight: 10,
    },
    animationDuration: 1200,
    animationEasing: 'cubicOut' as const,
    animationDelay: (_idx: number) => _idx * 80,
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '44%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 4,
        borderColor: '#0a0a1a',
        borderWidth: 2,
      },
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 13, fontWeight: 'bold', color: '#e0e6ed' },
        itemStyle: {
          shadowBlur: 20,
          shadowColor: 'rgba(0, 212, 255, 0.4)',
        },
      },
      data: data.map((s, i) => ({
        name: s.name,
        value: s.count,
        itemStyle: { color: palette[i % palette.length] },
      })),
    }],
  }
})

function getPlaceholderPie() {
  return {
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '44%'],
      label: { show: false },
      data: [{ value: 1, itemStyle: { color: 'rgba(0, 212, 255, 0.1)' } }],
    }],
  }
}

// ── Skill domain treemap ──
const treemapOption = computed(() => {
  const data = store.skillDomains
  if (!data?.length) {
    return getPlaceholderTreemap()
  }
  return {
    tooltip: {
      backgroundColor: 'rgba(15, 15, 35, 0.9)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: '#e0e6ed', fontSize: 12 },
      formatter: '{b}: {c}',
    },
    series: [{
      type: 'treemap',
      data: data.map(d => ({
        name: d.name,
        value: d.value,
        children: d.children?.map(c => ({
          name: c.name,
          value: c.value,
        })),
      })),
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      label: {
        show: true,
        formatter: '{b}',
        fontSize: 11,
        color: '#fff',
        textShadowColor: 'rgba(0,0,0,0.6)',
        textShadowBlur: 4,
      },
      itemStyle: {
        borderColor: '#0a0a1a',
        borderWidth: 2,
        gapWidth: 2,
      },
      levels: [{
        itemStyle: {
          borderColor: '#0a0a1a',
          borderWidth: 3,
          gapWidth: 3,
        },
      }, {
        colorSaturation: [0.35, 0.5],
        itemStyle: {
          borderColorSaturation: 0.6,
          gapWidth: 1,
          borderWidth: 1,
        },
      }],
      color: ['#00d4ff', '#7b61ff', '#00ff88', '#ff6b6b', '#ffd93d', '#6bcbff', '#a29bfe', '#ff9f43'],
    }],
  }
})

function getPlaceholderTreemap() {
  return {
    series: [{
      type: 'treemap',
      data: [
        { name: 'AI/ML', value: 30 },
        { name: '前端', value: 25 },
        { name: '后端', value: 20 },
        { name: '数据', value: 15 },
        { name: '运维', value: 10 },
      ],
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      label: { show: true, color: 'rgba(255,255,255,0.3)', fontSize: 11 },
      itemStyle: { borderColor: '#0a0a1a', borderWidth: 2 },
      color: ['rgba(0,212,255,0.15)', 'rgba(123,97,255,0.15)', 'rgba(0,255,136,0.15)', 'rgba(255,107,107,0.15)', 'rgba(255,217,61,0.15)'],
    }],
  }
}

// ── Quality trend dual-axis line chart ──
const trendOption = computed(() => {
  const trends = store.qualityTrends
  if (!trends?.length) return getPlaceholderTrend()
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 15, 35, 0.9)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: '#e0e6ed', fontSize: 12 },
    },
    legend: {
      top: 0,
      right: 0,
      textStyle: { color: 'rgba(224, 230, 237, 0.6)', fontSize: 10 },
      itemWidth: 12,
      itemHeight: 2,
    },
    grid: { top: 30, bottom: 24, left: 40, right: 40 },
    xAxis: {
      type: 'category',
      data: trends.map(t => t.date.slice(5)),
      axisLine: { lineStyle: { color: 'rgba(224, 230, 237, 0.15)' } },
      axisLabel: { color: 'rgba(224, 230, 237, 0.5)', fontSize: 10 },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: '分值',
        nameTextStyle: { color: 'rgba(224, 230, 237, 0.4)', fontSize: 10 },
        axisLabel: { color: 'rgba(224, 230, 237, 0.4)', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(224, 230, 237, 0.06)' } },
      },
      {
        type: 'value',
        name: '采集量',
        nameTextStyle: { color: 'rgba(224, 230, 237, 0.4)', fontSize: 10 },
        axisLabel: { color: 'rgba(224, 230, 237, 0.4)', fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '质量分',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: '#00d4ff', width: 2 },
        itemStyle: { color: '#00d4ff' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0, 212, 255, 0.2)' },
              { offset: 1, color: 'rgba(0, 212, 255, 0)' },
            ],
          },
        },
        data: trends.map(t => t.quality_score),
      },
      {
        name: '信任分',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: '#00ff88', width: 2 },
        itemStyle: { color: '#00ff88' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0, 255, 136, 0.15)' },
              { offset: 1, color: 'rgba(0, 255, 136, 0)' },
            ],
          },
        },
        data: trends.map(t => t.trust_score),
      },
      {
        name: '采集量',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#ffd93d', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#ffd93d' },
        data: trends.map(t => t.crawl_volume),
      },
    ],
  }
})

function getPlaceholderTrend() {
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() - (6 - i))
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  })
  return {
    grid: { top: 30, bottom: 24, left: 40, right: 40 },
    xAxis: {
      type: 'category',
      data: days,
      axisLine: { lineStyle: { color: 'rgba(224, 230, 237, 0.15)' } },
      axisLabel: { color: 'rgba(224, 230, 237, 0.3)', fontSize: 10 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: 'rgba(224, 230, 237, 0.3)', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(224, 230, 237, 0.06)' } },
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'none',
      lineStyle: { color: 'rgba(0, 212, 255, 0.3)', width: 2 },
      areaStyle: { color: 'rgba(0, 212, 255, 0.05)' },
      data: [0, 0, 0, 0, 0, 0, 0],
    }],
  }
}

// ── Emerging skills radar ──
const radarOption = computed(() => {
  const skills = store.emergingSkills
  if (!skills?.length) return getPlaceholderRadar()
  const top = skills.slice(0, 6)
  return {
    tooltip: {
      backgroundColor: 'rgba(15, 15, 35, 0.9)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: '#e0e6ed', fontSize: 12 },
    },
    radar: {
      indicator: top.map(s => ({
        name: s.name,
        max: 100,
      })),
      shape: 'polygon',
      splitNumber: 4,
      axisName: {
        color: 'rgba(224, 230, 237, 0.6)',
        fontSize: 10,
      },
      splitLine: {
        lineStyle: { color: 'rgba(224, 230, 237, 0.08)' },
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(0, 212, 255, 0.02)', 'rgba(0, 212, 255, 0.04)', 'rgba(0, 212, 255, 0.02)', 'rgba(0, 212, 255, 0.04)'],
        },
      },
      axisLine: {
        lineStyle: { color: 'rgba(224, 230, 237, 0.1)' },
      },
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: top.map(s => Math.round(s.growth_rate * 100)),
          name: '增长率',
          lineStyle: { color: '#00d4ff', width: 2 },
          itemStyle: { color: '#00d4ff' },
          areaStyle: { color: 'rgba(0, 212, 255, 0.15)' },
        },
        {
          value: top.map(s => Math.round(s.relevance * 100)),
          name: '相关度',
          lineStyle: { color: '#7b61ff', width: 2 },
          itemStyle: { color: '#7b61ff' },
          areaStyle: { color: 'rgba(123, 97, 255, 0.12)' },
        },
      ],
    }],
  }
})

function getPlaceholderRadar() {
  const indicators = ['React', 'Go', 'K8s', 'LLM', 'Rust', 'Vue'].map(n => ({ name: n, max: 100 }))
  return {
    radar: {
      indicator: indicators,
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: 'rgba(224, 230, 237, 0.3)', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(224, 230, 237, 0.06)' } },
      splitArea: { show: false },
      axisLine: { lineStyle: { color: 'rgba(224, 230, 237, 0.08)' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: [0, 0, 0, 0, 0, 0],
        lineStyle: { color: 'rgba(0, 212, 255, 0.2)' },
        itemStyle: { color: 'rgba(0, 212, 255, 0.2)' },
        areaStyle: { color: 'rgba(0, 212, 255, 0.05)' },
      }],
    }],
  }
}

// ── Pipeline mini timeline ──
const pipelineStages = computed(() => {
  if (store.pipelineTimeline.length) return store.pipelineTimeline
  return [
    { stage: '采集', status: 'waiting' as const, started_at: '', completed_at: null, records_processed: 0, progress: 0 },
    { stage: '去重', status: 'waiting' as const, started_at: '', completed_at: null, records_processed: 0, progress: 0 },
    { stage: '清洗', status: 'waiting' as const, started_at: '', completed_at: null, records_processed: 0, progress: 0 },
    { stage: '入库', status: 'waiting' as const, started_at: '', completed_at: null, records_processed: 0, progress: 0 },
    { stage: '图谱', status: 'waiting' as const, started_at: '', completed_at: null, records_processed: 0, progress: 0 },
  ]
})

const statusColor: Record<string, string> = {
  running: '#00d4ff',
  completed: '#00ff88',
  failed: '#ff6b6b',
  waiting: 'rgba(224, 230, 237, 0.2)',
}

// ── Event stream display ──
const eventIcon: Record<string, string> = {
  skill_update: '💡',
  match_event: '🎯',
  graph_update: '🔗',
  pipeline_event: '⚙️',
  extraction: '📄',
}

const eventSeverityColor: Record<string, string> = {
  info: 'rgba(0, 212, 255, 0.6)',
  success: 'rgba(0, 255, 136, 0.6)',
  warning: 'rgba(255, 217, 61, 0.6)',
  error: 'rgba(255, 107, 107, 0.6)',
}

function formatTime(ts: string) {
  if (!ts) return ''
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

// ── Auto-refresh timer ──
let refreshTimer: ReturnType<typeof setInterval> | null = null
const clockTick = ref(0)
let clockTimer: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  // Initial load
  await store.fetchAll()

  // SSE connection
  const sseUrl = '/api/v1/dashboard/realtime'
  const { connected } = useSSE(sseUrl, {
    onMessage: (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as RealtimeEvent
        if (data?.type) {
          store.addRealtimeEvent(data)
        }
      } catch {
        // Heartbeat or non-JSON message, ignore
      }
    },
    onError: () => {
      console.warn('[Dashboard] SSE connection failed, using polling fallback')
    },
    pollUrl: '/api/v1/dashboard/realtime-poll',
  })

  watch(connected, (val) => {
    store.sseConnected = val
  }, { immediate: true })

  // Periodic full refresh (30s)
  refreshTimer = setInterval(() => {
    store.fetchOverview()
  }, 30000)

  // Clock update
  clockTimer = setInterval(() => {
    clockTick.value++
  }, 1000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<template>
  <DashboardLayout
    title="StarMap 数据大屏"
    subtitle="实时数据监控与可视化"
  >
    <div class="dashboard-grid">
      <!-- ══════════════ TOP ROW: 6 KPI CARDS ══════════════ -->
      <div class="kpi-row">
        <div
          v-for="card in kpiCards"
          :key="card.label"
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
        </div>
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
  background: rgba(15, 15, 35, 0.6);
  border: 1px solid rgba(0, 212, 255, 0.1);
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  overflow: hidden;
  transition: all 0.3s ease;
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
  color: rgba(224, 230, 237, 0.5);
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
  background: rgba(15, 15, 35, 0.6);
  border: 1px solid rgba(0, 212, 255, 0.1);
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
  border-bottom: 1px solid rgba(0, 212, 255, 0.08);
  flex-shrink: 0;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(224, 230, 237, 0.85);
  letter-spacing: 0.02em;
}

.panel-badge {
  font-size: 9px;
  font-weight: 600;
  color: rgba(0, 212, 255, 0.6);
  background: rgba(0, 212, 255, 0.08);
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
  color: rgba(255, 107, 107, 0.7);
}

.sse-indicator.connected {
  color: rgba(0, 255, 136, 0.7);
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
  0%, 100% { opacity: 0.6; box-shadow: 0 0 4px rgba(0, 255, 136, 0.3); }
  50% { opacity: 1; box-shadow: 0 0 8px rgba(0, 255, 136, 0.6); }
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
  background: rgba(0, 212, 255, 0.15);
  border-radius: 2px;
}

.event-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(224, 230, 237, 0.04);
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
  color: rgba(224, 230, 237, 0.8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-detail {
  font-size: 10px;
  color: rgba(224, 230, 237, 0.4);
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
  color: rgba(224, 230, 237, 0.3);
  font-size: 12px;
}

.event-empty-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(0, 212, 255, 0.4);
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
  border: 2px solid rgba(224, 230, 237, 0.2);
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
  color: rgba(224, 230, 237, 0.8);
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
  background: rgba(224, 230, 237, 0.15);
  border-radius: 1px;
}

.connector-arrow {
  font-size: 14px;
  font-weight: 700;
  color: rgba(224, 230, 237, 0.2);
  line-height: 1;
}

.pipeline-stats {
  display: flex;
  justify-content: space-around;
  padding: 8px 12px;
  border-top: 1px solid rgba(0, 212, 255, 0.06);
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
  color: rgba(224, 230, 237, 0.85);
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 9px;
  color: rgba(224, 230, 237, 0.4);
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
