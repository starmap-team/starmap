<!--
  PipelineMonitor 卡死检测横幅（ Plan 03 从内联模板抽出）。
  强制推进 / 强制重置 操作按钮。
-->
<script setup lang="ts">
import { Close, Refresh } from '@element-plus/icons-vue'

defineProps<{
  reason: string
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'force-advance'): void
  (e: 'force-reset'): void
}>()
</script>

<template>
  <el-alert
    type="error"
    :closable="false"
    show-icon
    class="mb-4"
  >
    <template #title>
      <span style="font-weight: 700">⚠️ 流水线疑似卡死</span>
    </template>
    <div class="stuck-alert-content">
      <p style="margin: 4px 0">
        <strong>症状:</strong> {{ reason }}
      </p>
      <p style="margin: 4px 0">
        <strong>原因:</strong> Celery 任务因 event loop 错误失败, run 处于幽灵 running 状态
      </p>
      <p style="margin: 4px 0 12px 0">
        <strong>建议:</strong> 先尝试"强制推进"让 orchestrator 重新派发任务; 如果还卡再"强制重置"清除状态
      </p>
      <div class="stuck-actions">
        <el-button
          type="primary"
          :loading="loading"
          @click="emit('force-advance')"
        >
          <el-icon style="vertical-align: middle">
            <Refresh />
          </el-icon>
          强制推进
        </el-button>
        <el-button
          type="danger"
          :loading="loading"
          @click="emit('force-reset')"
        >
          <el-icon style="vertical-align: middle">
            <Close />
          </el-icon>
          强制重置
        </el-button>
      </div>
    </div>
  </el-alert>
</template>

<style scoped>
.stuck-alert-content {
  font-size: 13px;
  color: var(--foreground);
  line-height: 1.6;
}
.stuck-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
.stuck-actions :deep(.el-button) {
  font-weight: 600;
}
.mb-4 { margin-bottom: var(--space-4); }
</style>
