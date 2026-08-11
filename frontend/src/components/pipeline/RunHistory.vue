<!--
  PipelineMonitor 运行历史列表子组件（Phase 03 Plan 03 Task 8 实际实现）。
  渲染 /pipeline/runs 历史运行记录 + 每行操作（详情/重试/续跑/取消）。
-->
<script setup lang="ts">
import { VideoPlay } from '@element-plus/icons-vue'
import type { PipelineRun } from '@/stores/pipelineRun'

defineProps<{
  runs: PipelineRun[]
  loading?: boolean
  isAdmin: boolean
}>()

const emit = defineEmits<{
  (e: 'resume', runId: string): void
  (e: 'cancel', runId: string): void
}>()

function runTypeLabel(t: string): string {
  const labels: Record<string, string> = { full: '全量', incremental: '增量', source_sync: '单源同步' }
  return labels[t] ?? t
}
</script>

<template>
  <el-card
    v-loading="loading"
    shadow="never"
    class="run-history-card"
  >
    <template #header>
      <div class="panel-header">
        <span class="panel-title">运行历史</span>
        <el-tag
          v-if="runs.length"
          type="info"
          size="small"
          effect="plain"
        >
          {{ runs.length }} 条记录
        </el-tag>
      </div>
    </template>
    <div
      v-if="!runs.length"
      class="run-history-empty"
    >
      <p>暂无运行记录。触发流水线后，每次运行的状态、耗时和数据量将在此展示。</p>
    </div>
    <el-table
      v-else
      :data="runs"
      size="small"
      stripe
      empty-text="暂无数据"
    >
      <el-table-column
        label="运行时间"
        width="150"
      >
        <template #default="{ row }">
          {{ row.started_at ? new Date(row.started_at).toLocaleString() : '--' }}
        </template>
      </el-table-column>
      <el-table-column
        label="类型"
        width="80"
      >
        <template #default="{ row }">
          {{ runTypeLabel(row.run_type) }}
        </template>
      </el-table-column>
      <el-table-column
        label="状态"
        width="90"
      >
        <template #default="{ row }">
          <el-tag
            :type="row.status === 'completed' ? 'success' : row.status === 'running' ? 'primary' : row.status === 'failed' ? 'danger' : 'info'"
            size="small"
          >
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="总记录"
        width="80"
      >
        <template #default="{ row }">
          {{ row.total_records ?? 0 }}
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        min-width="180"
      >
        <template #default="{ row }">
          <template v-if="isAdmin">
            <el-button
              v-if="row.status === 'failed'"
              size="small"
              type="warning"
              link
              @click="emit('resume', row.id)"
            >
              <el-icon style="vertical-align: middle">
                <VideoPlay />
              </el-icon>
              续跑
            </el-button>
            <el-button
              v-if="row.status === 'running'"
              size="small"
              type="danger"
              link
              @click="emit('cancel', row.id)"
            >
              取消
            </el-button>
          </template>
          <span
            v-if="!isAdmin || (row.status !== 'failed' && row.status !== 'running')"
            class="run-history-muted"
          >--</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<style scoped>
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-title {
  font-weight: 600;
}
.run-history-empty {
  text-align: center;
  padding: var(--space-6) var(--space-4);
  color: var(--muted-foreground);
  font-size: 13px;
  background: var(--muted);
  border-radius: 6px;
}
.run-history-muted {
  color: var(--muted-foreground);
  font-size: 12px;
}
</style>
