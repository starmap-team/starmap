<script setup lang="ts">
/**
 * PipelineMonitor 状态 Hero 卡片 — 拆分
 *
 * 纯展示：根据 isRunning + stageSummary 显示流水线总体状态。
 * 无事件回调，无副作用。从 PipelineMonitor.vue:536-610 抽出。
 */
import { CircleCheck, Close, Loading, VideoPause, WarningFilled } from '@element-plus/icons-vue'

interface StageSummary {
  total: number
  completed: number
  running: number
  failed: number
  cancelled: number
  skipped: number
  totalRecords: number
  crawlRecords: number
  importRecords: number
  totalDurationMs: number
  importNote?: string   // 2026-08-12: 采集>0 但入库=0 时的重复说明（如"全部重复，未新增"）
}

const props = defineProps<{
  isRunning: boolean
  summary: StageSummary
}>()
</script>

<template>
  <el-card
    v-if="props.summary.total > 0"
    shadow="never"
    class="status-hero-card mb-4"
  >
    <div class="hero-content">
      <div class="hero-icon">
        <el-icon :size="32">
          <Loading
            v-if="props.isRunning"
            class="rotating"
          />
          <CircleCheck
            v-else-if="props.summary.failed === 0 && props.summary.cancelled === 0 && props.summary.completed === props.summary.total"
            color="#16a34a"
          />
          <WarningFilled
            v-else-if="props.summary.failed > 0"
            color="#dc2626"
          />
          <Close
            v-else-if="props.summary.cancelled > 0"
            color="#f59e0b"
          />
          <VideoPause
            v-else
            color="#94a3b8"
          />
        </el-icon>
      </div>
      <div class="hero-text">
        <div class="hero-title">
          <template v-if="props.isRunning">
            流水线正在执行中
          </template>
          <template v-else-if="props.summary.failed > 0">
            流水线异常终止 ({{ props.summary.failed }} 个阶段失败)
          </template>
          <template v-else-if="props.summary.cancelled > 0">
            流水线已取消
          </template>
          <template v-else-if="props.summary.completed === props.summary.total && props.summary.total > 0">
            流水线全部完成
          </template>
          <template v-else>
            流水线待机
          </template>
        </div>
        <div class="hero-detail">
          <span class="hero-pill completed">{{ props.summary.completed }} 已完成</span>
          <span
            v-if="props.summary.running > 0"
            class="hero-pill running"
          >{{ props.summary.running }} 运行中</span>
          <span
            v-if="props.summary.failed > 0"
            class="hero-pill failed"
          >{{ props.summary.failed }} 失败</span>
          <span
            v-if="props.summary.cancelled > 0"
            class="hero-pill cancelled"
          >{{ props.summary.cancelled }} 取消</span>
          <span
            v-if="props.summary.skipped > 0"
            class="hero-pill skipped"
          >{{ props.summary.skipped }} 跳过</span>
          <span class="hero-meta">
            采集 <strong>{{ props.summary.crawlRecords.toLocaleString() }}</strong> 条 →
            入库 <strong>{{ props.summary.importRecords.toLocaleString() }}</strong> 条,
            累计耗时 <strong>{{ (props.summary.totalDurationMs / 1000).toFixed(0) }}</strong> 秒
            <span
              v-if="props.summary.importNote"
              class="hero-note"
            >{{ props.summary.importNote }}</span>
          </span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
/* 2026-08-12: 采集>0 但入库=0 的重复说明 */
.hero-note {
  margin-left: 6px;
  font-size: 11px;
  color: var(--warning);
  font-weight: 600;
}
</style>
