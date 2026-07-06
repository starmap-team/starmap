<script setup lang="ts">
/**
 * 流水线 DAG 时间线视图
 * 展示 ETL DAG：爬虫采集 → (去重 ∥ 清洗) → 入库 → 图谱构建
 * 包含 fork/merge 箭头指示并行分支
 */
import PipelineStageCard from '@/components/PipelineStageCard.vue'
import type { PipelineStage } from '@/stores/pipeline'

defineProps<{
  timelineStages: PipelineStage[]
  retryingStages: Set<string>
  loading: boolean
  isRunning: boolean
}>()

const emit = defineEmits<{
  retry: [stageName: string]
}>()
</script>

<template>
  <el-card
    v-loading="loading"
    shadow="never"
    class="mb-4 timeline-card"
  >
    <template #header>
      <div class="panel-header">
        <span>流水线时间线 (DAG)</span>
        <el-tag
          v-if="isRunning"
          size="small"
          type="warning"
          effect="plain"
        >
          执行中
        </el-tag>
      </div>
    </template>
    <div class="pipeline-dag">
      <!-- Row 1: crawl -->
      <div class="dag-row dag-row-center">
        <div class="timeline-node">
          <PipelineStageCard
            :stage="timelineStages[0]"
            :retrying="retryingStages.has(timelineStages[0].name)"
            @retry="emit('retry', timelineStages[0].name)"
          />
        </div>
      </div>
      <!-- Arrow: crawl → (dedup + clean) -->
      <div class="dag-row dag-row-center">
        <div class="dag-fork">
          <div class="fork-line fork-left" />
          <div class="fork-line fork-right" />
        </div>
      </div>
      <!-- Row 2: dedup ∥ clean (parallel) -->
      <div class="dag-row dag-row-parallel">
        <div class="timeline-node">
          <PipelineStageCard
            :stage="timelineStages[1]"
            :retrying="retryingStages.has(timelineStages[1].name)"
            @retry="emit('retry', timelineStages[1].name)"
          />
        </div>
        <div class="parallel-label">
          并行
        </div>
        <div class="timeline-node">
          <PipelineStageCard
            :stage="timelineStages[2]"
            :retrying="retryingStages.has(timelineStages[2].name)"
            @retry="emit('retry', timelineStages[2].name)"
          />
        </div>
      </div>
      <!-- Arrow: (dedup + clean) → import -->
      <div class="dag-row dag-row-center">
        <div class="dag-merge">
          <div class="merge-line merge-left" />
          <div class="merge-line merge-right" />
        </div>
      </div>
      <!-- Row 3: import -->
      <div class="dag-row dag-row-center">
        <div class="timeline-node">
          <PipelineStageCard
            :stage="timelineStages[3]"
            :retrying="retryingStages.has(timelineStages[3].name)"
            @retry="emit('retry', timelineStages[3].name)"
          />
        </div>
      </div>
      <!-- Arrow: import → graph_sync -->
      <div class="dag-row dag-row-center">
        <div class="dag-arrow-down">
          <span class="arrow-line" />
          <span class="arrow-head">›</span>
        </div>
      </div>
      <!-- Row 4: graph_sync -->
      <div class="dag-row dag-row-center">
        <div class="timeline-node">
          <PipelineStageCard
            :stage="timelineStages[4]"
            :retrying="retryingStages.has(timelineStages[4].name)"
            @retry="emit('retry', timelineStages[4].name)"
          />
        </div>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
/* DAG 时间线 */
.timeline-card :deep(.el-card__header) {
  font-weight: 600;
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
.dag-row-parallel {
  justify-content: center;
  gap: var(--space-8);
}
.timeline-node :deep(.stage-card) {
  min-width: 180px;
  max-width: 200px;
}
.parallel-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  font-weight: 600;
  align-self: center;
}

/* DAG fork/merge arrows */
.dag-fork,
.dag-merge {
  display: flex;
  justify-content: center;
  width: 400px;
  height: 24px;
  position: relative;
}
.fork-line,
.merge-line {
  width: 2px;
  height: 24px;
  background: var(--muted-foreground);
  opacity: 0.4;
  position: absolute;
}
.fork-line.fork-left,
.merge-line.merge-left {
  left: 30%;
  transform: rotate(15deg);
}
.fork-line.fork-right,
.merge-line.merge-right {
  right: 30%;
  transform: rotate(-15deg);
}
.merge-line.merge-left {
  transform: rotate(-15deg);
}
.merge-line.merge-right {
  transform: rotate(15deg);
}
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

/* 面板头部 */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mb-4 { margin-bottom: var(--space-4); }

@media (max-width: 768px) {
  .dag-row-parallel { flex-direction: column; gap: var(--space-2); }
  .parallel-label { display: none; }
  .dag-fork, .dag-merge { display: none; }
  .timeline-node :deep(.stage-card) { min-width: 100%; max-width: 100%; }
}
</style>
