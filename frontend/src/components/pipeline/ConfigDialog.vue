<!--
  PipelineMonitor 流水线配置弹窗子组件（Phase 03 Plan 03 从内联模板抽出）。
-->
<script setup lang="ts">
/**
 * PipelineMonitor 流水线配置弹窗子组件（ Plan 03 从内联模板抽出）。
 * 使用本地 reactive 副本编辑，避免直接变更 prop；保存时回传副本。
 */
import { reactive, watch } from 'vue'
import type { PipelineConfig } from '@/stores/pipelineConfig'

const props = defineProps<{
  modelValue: boolean
  config: PipelineConfig | null
  saving?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'save', config: PipelineConfig): void
}>()

const localConfig = reactive<PipelineConfig>({
  stage_timeout: 60,
  worker_concurrency: 1,
  crawl_concurrency: 1,
  retry_max: 0,
  retry_backoff: 5,
})

watch(() => props.config, (cfg) => {
  if (cfg) Object.assign(localConfig, cfg)
}, { immediate: true })
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="流水线配置"
    width="480px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form
      v-if="config"
      label-width="120px"
    >
      <el-form-item label="阶段超时(秒)">
        <el-input-number
          v-model="localConfig.stage_timeout"
          :min="60"
          :max="7200"
          :step="60"
        />
      </el-form-item>
      <el-form-item label="Worker并发数">
        <el-input-number
          v-model="localConfig.worker_concurrency"
          :min="1"
          :max="16"
        />
      </el-form-item>
      <el-form-item label="爬取并发数">
        <el-input-number
          v-model="localConfig.crawl_concurrency"
          :min="1"
          :max="20"
        />
      </el-form-item>
      <el-form-item label="最大重试次数">
        <el-input-number
          v-model="localConfig.retry_max"
          :min="0"
          :max="10"
        />
      </el-form-item>
      <el-form-item label="重试间隔(秒)">
        <el-input-number
          v-model="localConfig.retry_backoff"
          :min="5"
          :max="300"
          :step="5"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">
        取消
      </el-button>
      <el-button
        v-if="config"
        type="primary"
        :loading="saving"
        @click="emit('save', localConfig)"
      >
        保存
      </el-button>
    </template>
  </el-dialog>
</template>
