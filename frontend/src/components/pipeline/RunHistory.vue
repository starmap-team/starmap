<!--
  PipelineMonitor 运行历史列表子组件（ Plan 03 Task 8 实际实现）。
  渲染 /pipeline/runs 历史运行记录 + 每行操作（详情/重试/续跑/取消）。

  2026-08-12 (pipeline 修复): 新增"详情"抽屉 —— 展示单次 run 的 stage 明细
  （状态/耗时/处理量/错误/警告）+ error_log，解决"看不到这条 run 真正完成了
  哪些成果"的疑问；"总记录"列加 tooltip 说明口径 = 本轮 crawl 新增入库数。
-->
<script setup lang="ts">
import { ref } from 'vue'
import { VideoPlay, View } from '@element-plus/icons-vue'
import type { PipelineRun, PipelineStage } from '@/stores/pipelineRun'

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

// ── 状态中文化（全盘友好性）: run/stage 内部英文标识 → 用户友好中文 ──
const RUN_STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  waiting: '排队中',
}

function statusLabel(status: string): string {
  return RUN_STATUS_LABELS[status] ?? status
}

function statusTagType(status: string): 'success' | 'primary' | 'danger' | 'info' | 'warning' {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'primary'
  if (status === 'failed') return 'danger'
  if (status === 'cancelled') return 'warning'
  return 'info'
}

// stage 状态多一个 skipped（阶段级）
const STAGE_STATUS_LABELS: Record<string, string> = {
  ...RUN_STATUS_LABELS,
  skipped: '已跳过',
}

function stageStatusLabel(status: string): string {
  return STAGE_STATUS_LABELS[status] ?? status
}

function stageTagType(status: string): 'success' | 'primary' | 'danger' | 'info' | 'warning' {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'primary'
  if (status === 'failed') return 'danger'
  if (status === 'cancelled') return 'warning'
  return 'info'
}

function fmtDuration(ms: number): string {
  if (!ms || ms <= 0) return '--'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const min = Math.floor(ms / 60000)
  const sec = ((ms % 60000) / 1000).toFixed(0)
  return `${min}m ${sec}s`
}

function fmtDateTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : '--'
}

// ── 详情抽屉状态 ──
const detailRun = ref<PipelineRun | null>(null)
const drawerVisible = ref(false)

function openDetail(row: PipelineRun) {
  detailRun.value = row
  drawerVisible.value = true
}

function stageRecordLabel(s: PipelineStage): string {
  const seen = s.records_seen || 0
  const inserted = s.records_processed || 0
 // 2026-08-12 (pipeline 联调): crawl 展示"处理(新增/重复)"，解释"为何入库 0"
  if (typeof s.records_new === 'number' && typeof s.records_duplicate === 'number') {
    return `${inserted}（新增 ${s.records_new} / 重复 ${s.records_duplicate}）`
  }
  if (seen > inserted && seen > 0) return `${inserted} / ${seen}` // X 入库, Y 抓到
  return String(inserted)
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
      @row-click="openDetail"
    >
      <el-table-column
        label="运行时间"
        width="150"
      >
        <template #default="{ row }">
          {{ fmtDateTime(row.started_at) }}
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
            :type="statusTagType(row.status)"
            size="small"
          >
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="总记录"
        width="90"
      >
        <template #default="{ row }">
          <!-- 2026-08-12: 口径 = 本轮 crawl 新增入库数（不再混入图回补/时间窗） -->
          <el-tooltip
            content="口径：本轮爬虫采集新增入库数（crawl 阶段 records_processed）。不再包含图谱回补与时间窗聚合，避免误导。"
            placement="top"
          >
            <span class="total-records-cell">{{ row.total_records ?? 0 }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        min-width="200"
      >
        <template #default="{ row }">
          <el-button
            size="small"
            type="primary"
            link
            :icon="View"
            @click.stop="openDetail(row)"
          >
            详情
          </el-button>
          <template v-if="isAdmin">
            <el-button
              v-if="row.status === 'failed'"
              size="small"
              type="warning"
              link
              @click.stop="emit('resume', row.id)"
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
              @click.stop="emit('cancel', row.id)"
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

  <!-- 详情抽屉：单次 run 各阶段明细 + error_log -->
  <el-drawer
    v-model="drawerVisible"
    :title="detailRun ? `运行详情 · ${fmtDateTime(detailRun.started_at)}` : '运行详情'"
    size="72%"
    append-to-body
  >
    <template v-if="detailRun">
      <!-- 运行元信息 -->
      <el-descriptions
        :column="2"
        border
        size="small"
        class="run-meta"
      >
        <el-descriptions-item label="运行 ID">
          {{ detailRun.id }}
        </el-descriptions-item>
        <el-descriptions-item label="类型">
          {{ runTypeLabel(detailRun.run_type) }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag
            :type="statusTagType(detailRun.status)"
            size="small"
          >
            {{ statusLabel(detailRun.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="开始时间">
          {{ fmtDateTime(detailRun.started_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="完成时间">
          {{ fmtDateTime(detailRun.completed_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="总记录（crawl 新增）">
          {{ detailRun.total_records ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item
          label="新增"
          width="120"
        >
          {{ detailRun.new_records ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item
          label="质量分"
          width="120"
        >
          {{ detailRun.quality_score ?? 0 }}
        </el-descriptions-item>
      </el-descriptions>

      <!-- 各阶段明细 -->
      <h4 class="drawer-section-title">
        阶段明细
      </h4>
      <el-table
        :data="detailRun.stages"
        size="small"
        border
        class="drawer-stages"
      >
        <el-table-column
          type="expand"
          width="36"
        >
          <template #default="{ row }">
            <div class="stage-detail-body">
              <div
                v-if="(row.errors?.length ?? 0) > 0"
                class="stage-detail-block"
              >
                <div class="block-label block-label-danger">
                  错误
                </div>
                <div
                  v-for="(e, i) in row.errors"
                  :key="'e' + i"
                  class="block-line"
                >
                  {{ e }}
                </div>
              </div>
              <div
                v-if="(row.warnings?.length ?? 0) > 0"
                class="stage-detail-block"
              >
                <div class="block-label block-label-warning">
                  警告（非致命）
                </div>
                <div
                  v-for="(w, i) in row.warnings"
                  :key="'w' + i"
                  class="block-line"
                >
                  {{ w }}
                </div>
              </div>
              <div
                v-if="row.current_activity"
                class="stage-detail-block"
              >
                <div class="block-label">
                  活动
                </div>
                <div class="block-line">
                  {{ row.current_activity }}
                </div>
              </div>
              <div
                v-if="row.sub_breakdown && Object.keys(row.sub_breakdown).length"
                class="stage-detail-block"
              >
                <div class="block-label">
                  子项分解（按数据源）
                </div>
                <div
                  v-for="(v, k) in row.sub_breakdown"
                  :key="k"
                  class="block-line sub-breakdown-line"
                >
                  {{ k }}: {{ v }}
                </div>
              </div>
              <div
                v-if="(row.recent_samples?.length ?? 0) > 0"
                class="stage-detail-block"
              >
                <div class="block-label">
                  最近样本
                </div>
                <div
                  v-for="(s, i) in row.recent_samples"
                  :key="'s' + i"
                  class="block-line"
                >
                  {{ s.title || s.skill || s.url || JSON.stringify(s).slice(0, 60) }}
                </div>
              </div>
              <div
                v-if="(row.errors?.length ?? 0) === 0 && (row.warnings?.length ?? 0) === 0 && !row.current_activity"
                class="block-line muted"
              >
                无更多明细
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="阶段"
          prop="name"
          width="110"
        />
        <el-table-column
          label="状态"
          width="90"
        >
          <template #default="{ row }">
            <el-tag
              :type="stageTagType(row.status)"
              size="small"
            >
              {{ stageStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="耗时"
          width="90"
        >
          <template #default="{ row }">
            {{ fmtDuration(row.duration_ms ?? row.elapsed_ms ?? 0) }}
          </template>
        </el-table-column>
        <el-table-column
          label="处理量"
          width="90"
        >
          <template #default="{ row }">
            {{ stageRecordLabel(row) }}
          </template>
        </el-table-column>
        <el-table-column
          label="错误"
          width="70"
        >
          <template #default="{ row }">
            <span :class="{ 'error-count': (row.errors?.length ?? 0) > 0 }">{{ row.errors?.length ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="警告"
          width="70"
        >
          <template #default="{ row }">
            <span :class="{ 'warning-count': (row.warnings?.length ?? 0) > 0 }">{{ row.warnings?.length ?? 0 }}</span>
          </template>
        </el-table-column>
      </el-table>

      <!-- 错误日志 -->
      <h4 class="drawer-section-title">
        错误日志
      </h4>
      <pre class="error-log-box">{{ detailRun.error_log || '（无）' }}</pre>
    </template>
  </el-drawer>
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
.total-records-cell {
  cursor: help;
  text-decoration: underline dotted var(--muted-foreground);
}
/* 详情抽屉 */
.run-meta {
  margin-bottom: var(--space-4);
}
.drawer-section-title {
  font-size: var(--font-size-sm);
  font-weight: 700;
  margin: var(--space-4) 0 var(--space-2);
  color: var(--foreground);
}
.stage-detail-body {
  padding: 4px 8px;
}
.stage-detail-block {
  margin-bottom: 6px;
}
.block-label {
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 2px;
  color: var(--muted-foreground);
}
.block-label-danger { color: var(--destructive); }
.block-label-warning { color: var(--warning); }
.block-line {
  font-size: 12px;
  line-height: 1.5;
  word-break: break-all;
  color: var(--foreground);
}
.sub-breakdown-line {
  font-size: 11px;
  color: var(--muted-foreground);
}
.block-line.muted { color: var(--muted-foreground); font-style: italic; }
.error-count { color: var(--destructive); font-weight: 600; }
.warning-count { color: var(--warning); font-weight: 600; }
.error-log-box {
  background: var(--muted);
  border-radius: 6px;
  padding: var(--space-3);
  font-size: 12px;
  line-height: 1.6;
  color: var(--destructive);
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
</style>
