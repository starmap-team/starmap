<!--
  PipelineMonitor 运行历史子组件（D-03 Task 8 拆分骨架）

  状态：scaffold（zero behavior change）
  下一步：迁移 /pipeline/runs 渲染 + 单 run 操作（cancel/retry/resume）
-->
<template>
  <div v-if="false" />
</template>

<script setup lang="ts">
interface Props {
  runs: Array<{
    id: string
    status: string
    startedAt: string
  }>
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'cancel', runId: string): void
  (e: 'retry', runId: string): void
  (e: 'resume', runId: string): void
  (e: 'force-advance', runId: string): void
  (e: 'force-reset', runId: string): void
}>()
</script>