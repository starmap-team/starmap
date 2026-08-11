<!--
  PipelineMonitor 定时调度表单子组件（D-03 Task 8 拆分骨架）

  状态：scaffold（zero behavior change）
  下一步：迁移 Cron 输入校验 + 调度 CRUD（Task 11 详细实施）
-->
<template>
  <div v-if="false" />
</template>

<script setup lang="ts">
interface Props {
  schedules: Array<{
    id: string
    name: string
    cron: string
    enabled: boolean
  }>
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'create', data: { name: string; cron: string }): void
  (e: 'update', id: string, data: { name?: string; cron?: string; enabled?: boolean }): void
  (e: 'delete', id: string): void
  (e: 'trigger', id: string): void
}>()
</script>