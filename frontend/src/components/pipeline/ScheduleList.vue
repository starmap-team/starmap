<!--
  PipelineMonitor 定时调度列表子组件（ Plan 03 从内联模板抽出）。
-->
<script setup lang="ts">
import { QuestionFilled, Timer } from '@element-plus/icons-vue'
import { RUN_TYPE_LABELS } from '@/constants/labels'
import type { PipelineSchedule } from '@/stores/pipelineConfig'

defineProps<{
  schedules: PipelineSchedule[]
  isAdmin: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle', schedule: PipelineSchedule): void
  (e: 'trigger', schedule: PipelineSchedule): void
  (e: 'delete', id: string): void
  (e: 'add'): void
}>()
</script>

<template>
  <el-card
    v-loading="loading"
    shadow="never"
    class="mb-4"
  >
    <template #header>
      <div class="panel-header">
        <div>
          <span class="panel-title">定时调度 (Cron)</span>
          <el-tooltip
            content="用 Cron 表达式设置流水线自动执行计划。例如 '0 2 * * *' 表示每天凌晨 2 点。点击'新增'创建调度；点击'立即触发'手动执行。点击'启用'开关控制调度是否生效。"
            placement="top"
          >
            <el-icon class="help-icon">
              <QuestionFilled />
            </el-icon>
          </el-tooltip>
        </div>
        <el-button
          v-if="isAdmin"
          size="small"
          :icon="Timer"
          @click="emit('add')"
        >
          新增调度
        </el-button>
      </div>
    </template>
    <div
      v-if="!schedules.length"
      class="schedule-empty"
    >
      <p>暂无定时调度。点击右上角"新增调度"创建第一个 Cron 计划。</p>
    </div>
    <el-table
      v-else
      :data="schedules"
      size="small"
      stripe
      empty-text="暂无数据"
    >
      <el-table-column
        prop="name"
        label="名称"
        width="140"
      />
      <el-table-column
        prop="cron_expression"
        label="Cron 表达式"
        width="140"
      />
      <!-- D8: 展示调度自选的爬取源（空 = 全部） -->
      <el-table-column
        label="爬取源"
        min-width="140"
      >
        <template #default="{ row }">
          <template v-if="row.selected_sources?.length">
            <el-tag
              v-for="s in row.selected_sources"
              :key="s"
              size="small"
              type="info"
              effect="plain"
              class="mr-1"
            >
              {{ s }}
            </el-tag>
          </template>
          <span v-else>全部源</span>
        </template>
      </el-table-column>
      <el-table-column
        prop="run_type"
        label="类型"
        width="100"
      >
        <template #default="{ row }">
          <el-tag
            :type="row.run_type === 'full' ? '' : 'info'"
            size="small"
          >
            {{ RUN_TYPE_LABELS[row.run_type as 'full' | 'incremental'] ?? row.run_type }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="启用"
        width="80"
      >
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled"
            size="small"
            @change="emit('toggle', row)"
          />
        </template>
      </el-table-column>
      <el-table-column
        label="上次运行"
        width="160"
      >
        <template #default="{ row }">
          {{ row.last_run_at ? new Date(row.last_run_at).toLocaleString() : '--' }}
        </template>
      </el-table-column>
      <el-table-column
        label="下次运行"
        width="160"
      >
        <template #default="{ row }">
          {{ row.enabled && row.next_run_at ? new Date(row.next_run_at).toLocaleString() : '--' }}
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        width="160"
      >
        <template #default="{ row }">
          <el-button
            size="small"
            type="primary"
            link
            @click="emit('trigger', row)"
          >
            立即执行
          </el-button>
          <el-button
            size="small"
            type="danger"
            link
            @click="emit('delete', row.id)"
          >
            删除
          </el-button>
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
  margin-right: 6px;
}
.help-icon {
  color: var(--muted-foreground);
  font-size: 13px;
  cursor: help;
}
.help-icon:hover { color: var(--primary); }
.schedule-empty {
  text-align: center;
  padding: var(--space-6) var(--space-4);
  color: var(--muted-foreground);
  font-size: 13px;
  background: var(--muted);
  border-radius: 6px;
}
.mb-4 { margin-bottom: var(--space-4); }
</style>
