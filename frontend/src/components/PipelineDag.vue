<script setup lang="ts">
/**
 * 流水线 DAG 时间线视图 ( 增强)
 * DAG 节点本身集成实时活动数据 - 不再需要单独的实时面板
 * 展示 ETL DAG：爬虫采集 → 去重 → 清洗 → 入库 → 图谱构建（ 串行化）
 * 箭头表示阶段间串行依赖（clean 依赖 dedup）
 */
import { computed } from 'vue'
import { Connection, Loading } from '@element-plus/icons-vue'
import PipelineStageCard from '@/components/PipelineStageCard.vue'
import type { PipelineStage, LiveActivityEvent } from '@/stores/pipelineRun'

const props = defineProps<{
  timelineStages: PipelineStage[]
  retryingStages: Set<string>
  blockedStages: Set<string>
  loading: boolean
  isRunning: boolean
  actionLoading?: boolean
  liveActivity?: Record<string, LiveActivityEvent>
}>()

const emit = defineEmits<{
  retry: [stageName: string]
  resume: []
}>()

// 整体进度（按 stages 加权平均）
const overallProgress = computed(() => {
  const active = props.timelineStages.filter(s => s.status !== 'skipped')
  if (!active.length) return 0
  let completedWeight = 0
  for (const s of active) {
    if (s.status === 'completed') completedWeight += 1
    else if (s.status === 'running') completedWeight += (s.progress || 0)
  }
  return Math.round((completedWeight / active.length) * 100)
})

//: 阶段状态计数 (解决"17% 看不出含义")
const completedCount = computed(() => props.timelineStages.filter(s => s.status === 'completed').length)
const runningCount = computed(() => props.timelineStages.filter(s => s.status === 'running').length)
const failedCount = computed(() => props.timelineStages.filter(s => s.status === 'failed').length)
const cancelledCount = computed(() => props.timelineStages.filter(s => s.status === 'cancelled').length)
const totalCount = computed(() => props.timelineStages.filter(s => s.status !== 'skipped').length)
const anyCompleted = computed(() => completedCount.value > 0)
const anyFailed = computed(() => failedCount.value > 0)

// 进度条颜色
const progressColor = computed(() => {
  if (anyFailed.value) return '#dc2626'
  if (cancelledCount.value > 0 && completedCount.value === 0) return '#f59e0b'
  if (runningCount.value > 0) return '#3b82f6'
  if (anyCompleted.value && completedCount.value === totalCount.value) return '#16a34a'
  return '#94a3b8'
})

function getStageLive(stageName: string): LiveActivityEvent | null {
  return props.liveActivity?.[stageName] || null
}

// 2026-08-21 (P0-2): 作业身份 —— 从任一 stage 取当前 run 标识（后端 /stages
// 每个 stage 都带 run_id/run_status）。展示"这是哪一次运行"，避免不同 run 混淆。
const currentRunId = computed(() => props.timelineStages[0]?.run_id || '')
const currentRunStatus = computed(() => props.timelineStages[0]?.run_status || '')

// import 阶段的"剩余待续"提示（从 current_activity 解析"剩余 N 条待续跑"）
const importRemainingText = computed(() => {
  const importStage = props.timelineStages.find(s => s.name === 'import')
  const activity = importStage?.current_activity || ''
  const m = activity.match(/剩余\s*(\d+)\s*条待续跑/)
  if (m) return `剩余 ${m[1]} 条待续跑`
  return ''
})

// import 失败且有剩余待续 → 显示「继续处理剩余 N 条」按钮（断点续跑）
const showResumeRemaining = computed(() => {
  const importStage = props.timelineStages.find(s => s.name === 'import')
  return importStage?.status === 'failed' && importRemainingText.value !== ''
})
</script>

<template>
  <el-card
    v-loading="loading"
    shadow="never"
    class="mb-4 timeline-card"
  >
    <template #header>
      <div class="panel-header">
        <div class="panel-title">
          <el-icon style="vertical-align: middle">
            <Connection />
          </el-icon>
          <span>流水线时间线 (DAG)</span>
          <!-- 2026-08-21 (P0-2): 作业身份 —— 显示当前 run 短 ID，避免不同 run 混淆 -->
          <span
            v-if="currentRunId"
            class="run-id-tag"
            :title="`运行 ID: ${currentRunId} · 状态: ${currentRunStatus}`"
          >#{{ currentRunId.slice(0, 8) }}</span>
          <!--: 阶段完成计数 (解决"17% 看不出含义") -->
          <span class="stage-count">
            {{ completedCount }}/{{ totalCount }} 阶段已完成
            <span
              v-if="runningCount > 0"
              class="running-tag"
            >· {{ runningCount }} 运行中</span>
            <span
              v-if="failedCount > 0"
              class="failed-tag"
            >· {{ failedCount }} 失败</span>
            <span
              v-if="cancelledCount > 0"
              class="cancelled-tag"
            >· {{ cancelledCount }} 取消</span>
          </span>
        </div>
        <div class="header-right">
          <!--: 始终显示进度条 + 文字说明 -->
          <div class="overall-progress">
            <span class="overall-label">{{ isRunning ? '执行中' : (anyFailed ? '异常' : (anyCompleted ? '已完成' : '待机')) }}</span>
            <el-progress
              :percentage="overallProgress"
              :stroke-width="8"
              :show-text="false"
              :color="progressColor"
              class="overall-bar"
            />
            <span
              class="overall-text"
              :style="{ color: progressColor }"
            >{{ overallProgress }}%</span>
          </div>
          <el-tag
            v-if="isRunning"
            size="small"
            type="warning"
            effect="plain"
            class="status-badge"
          >
            <el-icon
              class="rotating"
              :size="11"
            >
              <Loading />
            </el-icon>
            执行中
          </el-tag>
          <el-tag
            v-else-if="timelineStages.some(s => s.status === 'completed')"
            size="small"
            type="success"
            effect="plain"
          >
            已完成
          </el-tag>
          <el-tag
            v-else-if="timelineStages.some(s => s.status === 'failed')"
            size="small"
            type="danger"
            effect="plain"
          >
            失败
          </el-tag>
          <el-tag
            v-else
            size="small"
            type="info"
            effect="plain"
          >
            待机
          </el-tag>
        </div>
      </div>
    </template>
    <div class="pipeline-dag">
      <!-- Row 1: crawl -->
      <div class="dag-row dag-row-center">
        <div class="timeline-node">
          <PipelineStageCard
            :stage="timelineStages[0]"
            :live-activity="getStageLive(timelineStages[0]?.name)"
            :retrying="retryingStages.has(timelineStages[0]?.name || '')"
            :blocked="blockedStages?.has(timelineStages[0]?.name || '') ?? false"
            @retry="emit('retry', timelineStages[0].name)"
          />
        </div>
      </div>
      <!-- Arrow: crawl → dedup -->
      <div class="dag-row dag-row-center">
        <div class="dag-arrow-down">
          <span class="arrow-line" />
          <span class="arrow-head">›</span>
        </div>
      </div>
      <!-- Row 2: dedup -->
      <div class="dag-row dag-row-center">
        <div class="timeline-node">
          <PipelineStageCard
            :stage="timelineStages[1]"
            :live-activity="getStageLive(timelineStages[1]?.name)"
            :retrying="retryingStages.has(timelineStages[1]?.name || '')"
            :blocked="blockedStages?.has(timelineStages[1]?.name || '') ?? false"
            @retry="emit('retry', timelineStages[1].name)"
          />
        </div>
      </div>
      <!-- Arrow: dedup → clean ( Plan 02 Task 2: clean 依赖 dedup，串行) -->
      <div class="dag-row dag-row-center">
        <div class="dag-arrow-down">
          <span class="arrow-line" />
          <span class="arrow-head">›</span>
        </div>
      </div>
      <!-- Row 3: clean -->
      <div class="dag-row dag-row-center">
        <div class="timeline-node">
          <PipelineStageCard
            :stage="timelineStages[2]"
            :live-activity="getStageLive(timelineStages[2]?.name)"
            :retrying="retryingStages.has(timelineStages[2]?.name || '')"
            :blocked="blockedStages?.has(timelineStages[2]?.name || '') ?? false"
            @retry="emit('retry', timelineStages[2].name)"
          />
        </div>
      </div>
      <!-- Arrow: clean → import -->
      <div class="dag-row dag-row-center">
        <div class="dag-arrow-down">
          <span class="arrow-line" />
          <span class="arrow-head">›</span>
        </div>
      </div>
      <!-- Row 4: import -->
      <div class="dag-row dag-row-center">
        <div class="timeline-node">
          <PipelineStageCard
            :stage="timelineStages[3]"
            :live-activity="getStageLive(timelineStages[3]?.name)"
            :retrying="retryingStages.has(timelineStages[3]?.name || '')"
            :blocked="blockedStages?.has(timelineStages[3]?.name || '') ?? false"
            @retry="emit('retry', timelineStages[3].name)"
          />
        </div>
      </div>
      <!-- 2026-08-21 (P0-2): import 剩余待续提示 + 一键继续（断点续跑显性化） -->
      <div
        v-if="importRemainingText || showResumeRemaining"
        class="dag-row dag-row-center"
      >
        <div class="import-remaining-bar">
          <span class="remaining-text">📋 {{ importRemainingText }}</span>
          <el-button
            v-if="showResumeRemaining"
            type="primary"
            size="small"
            @click="emit('resume')"
          >
            继续处理剩余 {{ importRemainingText.replace('剩余 ', '').replace(' 条待续跑', '') }} 条
          </el-button>
        </div>
      </div>
      <!-- Arrow: import → graph_sync -->
      <div class="dag-row dag-row-center">
        <div class="dag-arrow-down">
          <span class="arrow-line" />
          <span class="arrow-head">›</span>
        </div>
      </div>
      <!-- Row 5: graph_sync (DAG 终点) -->
      <div class="dag-row dag-row-center">
        <div class="timeline-node">
          <PipelineStageCard
            :stage="timelineStages[4]"
            :live-activity="getStageLive(timelineStages[4]?.name)"
            :retrying="retryingStages.has(timelineStages[4]?.name || '')"
            :blocked="blockedStages?.has(timelineStages[4]?.name || '') ?? false"
            @retry="emit('retry', timelineStages[4].name)"
          />
        </div>
      </div>
      <!---01: timeseries 移出核心 DAG, Row 6 删除 -->
    </div>
  </el-card>
</template>

<style scoped>
.timeline-card :deep(.el-card__header) {
  font-weight: 600;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.panel-title {
  font-weight: 600;
  font-size: var(--font-size-base);
  color: var(--foreground);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.stage-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--muted-foreground);
  margin-left: var(--space-2);
}
.running-tag { color: #3b82f6; font-weight: 600; }

/* 2026-08-21 (P0-2): 作业身份 + 剩余待续 */
.run-id-tag {
  font-size: 11px;
  color: #64748b;
  background: var(--bg-muted, #f1f5f9);
  border-radius: 4px;
  padding: 1px 6px;
  font-family: ui-monospace, monospace;
}
.import-remaining-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: var(--warning-ghost, #fef3c7);
  border: 1px solid var(--warning, #f59e0b);
  border-radius: 6px;
  font-size: 12px;
}
.remaining-text { color: var(--warning, #b45309); font-weight: 500; }
.failed-tag { color: #dc2626; font-weight: 600; }
.cancelled-tag { color: #f59e0b; font-weight: 600; }
.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.overall-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 200px;
}
.overall-label {
  font-size: 11px;
  color: var(--muted-foreground);
  white-space: nowrap;
}
.overall-bar {
  flex: 1;
  min-width: 100px;
}
.overall-text {
  font-size: 11px;
  font-weight: 600;
  color: var(--foreground);
  font-variant-numeric: tabular-nums;
  min-width: 32px;
  text-align: right;
}
.status-badge {
  display: flex;
  align-items: center;
  gap: 3px;
}
.rotating {
  animation: rotate 1s linear infinite;
}
@keyframes rotate {
  to { transform: rotate(360deg); }
}

.pipeline-dag {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  padding: var(--space-4) 0;
}
.dag-row {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}
.dag-row-center {
  justify-content: center;
}
.timeline-node {
  position: relative;
}

/* DAG 串行箭头（ Plan 02 Task 2: clean 依赖 dedup，取消 fork/merge） */
.dag-arrow-down {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.dag-arrow-down .arrow-line {
  display: block;
  width: 2px;
  height: 16px;
  background: var(--muted-foreground);
  opacity: 0.4;
}
.dag-arrow-down .arrow-head {
  font-size: 14px;
  font-weight: 700;
  color: var(--muted-foreground);
  opacity: 0.4;
  transform: rotate(90deg);
}

.mb-4 { margin-bottom: var(--space-4); }

@media (max-width: 768px) {
 /* 旧并行布局的 mobile 适配已删除（ Plan 02 Task 2: DAG 串行化） */
  .overall-progress { min-width: 120px; }
}
</style>
