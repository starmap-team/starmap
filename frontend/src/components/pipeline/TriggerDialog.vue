<!--
  PipelineMonitor 触发对话框子组件（Phase 03 Plan 03 Task 8 实际迁移）。
  T7 引导：顶部说明 + selectedStages 多选 tooltip + 前置条件提示。
-->
<script setup lang="ts">
import { VideoPlay } from '@element-plus/icons-vue'
import { RUN_TYPE_LABELS } from '@/constants/labels'

defineProps<{
  modelValue: boolean
  runType: 'full' | 'incremental'
  selectedStages: string[]
  availableStages: string[]
  stageLabels: Record<string, string>
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'update:runType', value: 'full' | 'incremental'): void
  (e: 'update:selectedStages', value: string[]): void
  (e: 'submit'): void
}>()
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="触发流水线"
    width="480px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="mb-4"
      title="触发后将按 DAG 顺序执行所有选中阶段"
      description="未选中的阶段将标记为 skipped。至少需要 1 个启用的数据源才能采集数据。全量模式重跑所有数据，增量模式仅处理新增记录。"
    />
    <el-form label-width="80px">
      <el-form-item label="运行类型">
        <el-radio-group
          :model-value="runType"
          @update:model-value="emit('update:runType', $event as 'full' | 'incremental')"
        >
          <el-radio value="full">
            {{ RUN_TYPE_LABELS.full }}
          </el-radio>
          <el-radio value="incremental">
            {{ RUN_TYPE_LABELS.incremental }}
          </el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="执行阶段">
        <el-tooltip
          content="可选择部分阶段重跑（如仅重跑 import），未选阶段将标记为 skipped"
          placement="top"
          effect="dark"
        >
          <el-checkbox-group
            :model-value="selectedStages"
            @update:model-value="emit('update:selectedStages', $event as string[])"
          >
            <el-checkbox
              v-for="name in availableStages"
              :key="name"
              :value="name"
            >
              {{ stageLabels[name] || name }}
            </el-checkbox>
          </el-checkbox-group>
        </el-tooltip>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">
        取消
      </el-button>
      <el-button
        type="primary"
        :icon="VideoPlay"
        :disabled="selectedStages.length === 0"
        :loading="loading"
        @click="emit('submit')"
      >
        启动
      </el-button>
    </template>
  </el-dialog>
</template>
