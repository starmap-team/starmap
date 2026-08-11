<!--
  PipelineMonitor 触发对话框子组件（D-03 Task 8 拆分骨架）

  当前为占位骨架 — PipelineMonitor.vue 内联触发对话框完整保留运行。
  本文件提供 props 接口与命名约定供未来组件提取使用。

  状态：scaffold（zero behavior change）
  下一步：实际迁移触发对话框逻辑（dialog open/close/selectedStages/submit）
-->
<template>
  <div v-if="false">
    <!-- 占位：未来实际挂载点 -->
  </div>
</template>

<script setup lang="ts">
/**
 * TriggerDialog 触发对话框 props 契约（未来实际迁移时使用）
 */
interface Props {
  modelValue: boolean
  availableStages: string[]
  selectedStages: string[]
  loading?: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'update:selectedStages', value: string[]): void
  (e: 'submit', stages: string[]): void
}>()
</script>
