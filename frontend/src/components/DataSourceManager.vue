<script setup lang="ts">
/**
 * 数据源管理面板 (Phase 3.8.4 增强版)
 *
 * 核心功能:
 * 1. 实时执行状态 — 通过 SSE 事件流显示每源当前在做什么
 * 2. 数据源管理操作 — 启用/禁用切换 + 平台映射显示 + 原因说明
 * 3. 配置可视化 — 显示每源的爬虫类型/平台/关键词/max_count
 * 4. 帮助提示 — 每个数据源都有清晰的"为什么启用/为什么禁用"说明
 */
import { computed } from 'vue'
import {
  Connection, VideoPlay, VideoPause, CircleCheck, Warning, QuestionFilled, Loading,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSourceNameLabel } from '@/composables/useDataSourceCharts'
import type { LiveActivityEvent } from '@/stores/pipelineRun'
import type { DataSourceDetail } from '@/types/datasource'

// Spider 注册表 (与后端 executor.py 一致)
const SUPPORTED_SPIDERS = {
  bosszhipin: { label: 'BOSS直聘', icon: '📋' },
  '51job': { label: '前程无忧', icon: '💼' },
  lagou: { label: '拉勾', icon: '🚀' },
} as const

interface DataSourceWithStatus extends DataSourceDetail {
  liveStatus?: 'idle' | 'crawling' | 'success' | 'skipped' | 'failed'
  liveMessage?: string
  liveRecords?: number
}

const props = defineProps<{
  dataSources: DataSourceDetail[]
  liveActivity: Record<string, LiveActivityEvent>
  currentStageProgress: number
  isRunning: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  toggleSource: [sourceId: string, enabled: boolean]
  testSource: [sourceId: string]
}>()

// === 计算属性 ===
const enhancedSources = computed<DataSourceWithStatus[]>(() => {
  return props.dataSources.map((ds: DataSourceWithStatus) => {
    // 实时状态判断
    let liveStatus: DataSourceWithStatus['liveStatus'] = 'idle'
    let liveMessage = ''
    let liveRecords = 0
    if (props.isRunning) {
      // 从当前 stage 活动推算该源状态
      const currentActivity = Object.values(props.liveActivity)[0]
      if (currentActivity) {
        const subBreakdown = currentActivity.sub_breakdown || {}
        const sourceStatus = subBreakdown[ds.name]
        if (sourceStatus === -1 || sourceStatus === -2) {
          liveStatus = 'skipped'
        } else if (sourceStatus !== undefined) {
          liveStatus = 'crawling'
          liveMessage = `已采 ${sourceStatus} 条`
          liveRecords = sourceStatus as number
        } else {
          liveStatus = 'idle'
        }
      }
    }

    return {
      ...ds,
      liveStatus,
      liveMessage,
      liveRecords,
    } as DataSourceWithStatus
  })
})

// 按类型分组
const crawlerSources = computed(() =>
  enhancedSources.value.filter(s => s.source_type === 'crawler')
)
const otherSources = computed(() =>
  enhancedSources.value.filter(s => s.source_type !== 'crawler')
)

const enabledCrawlers = computed(() =>
  crawlerSources.value.filter(s => {
    const platform = String(s.config?.platform || '')
    return platform in SUPPORTED_SPIDERS && !s.config?.disabled
  })
)

const totalEnabled = computed(() => enabledCrawlers.value.length)

// Phase 3.8.5: 当前活动详情 (从 liveActivity 中提取最新一条)
const currentActivityDetails = computed(() => {
  if (!props.liveActivity) return null
  const entries = Object.values(props.liveActivity)
  if (!entries.length) return null
  // 取最新一条 (有 progress 最高或最近的)
  return entries.sort((a, b) => (b.progress || 0) - (a.progress || 0))[0]
})

const hasSubBreakdown = computed(() => {
  const d = currentActivityDetails.value
  return !!(d?.sub_breakdown && Object.keys(d.sub_breakdown).length > 0)
})

// 平台映射说明
function platformInfo(ds: DataSourceDetail) {
  const platform = String(ds.config?.platform || '')
  if (platform in SUPPORTED_SPIDERS) {
    const info = SUPPORTED_SPIDERS[platform as keyof typeof SUPPORTED_SPIDERS]
    return { available: true, label: info.label, icon: info.icon }
  }
  return { available: false, label: platform || '未配置', icon: '❓' }
}

// 状态徽章
function statusBadge(ds: DataSourceWithStatus) {
  if (ds.liveStatus === 'crawling') {
    return { class: 'status-running', label: '采集中', color: '#3b82f6' }
  }
  if (ds.liveStatus === 'skipped') {
    return { class: 'status-skipped', label: '已跳过', color: '#94a3b8' }
  }
  if (ds.liveStatus === 'success') {
    return { class: 'status-completed', label: '完成', color: '#16a34a' }
  }
  if (ds.liveStatus === 'failed') {
    return { class: 'status-failed', label: '失败', color: '#dc2626' }
  }
  if (ds.config?.disabled) {
    return { class: 'status-paused', label: '已禁用', color: '#94a3b8' }
  }
  return { class: 'status-idle', label: '待机', color: '#94a3b8' }
}

// 切换启用
async function onToggle(ds: DataSourceWithStatus) {
  const cfg = ds.config || {}
  const willDisable = !cfg.disabled
  const action = willDisable ? '禁用' : '启用'
  try {
    const sourceLabel = getSourceNameLabel(ds.name)
    await ElMessageBox.confirm(
      willDisable
        ? `确认禁用 ${sourceLabel}？禁用后该源将不会在流水线中执行。`
        : `确认启用 ${sourceLabel}？启用后将在下次流水线中执行。`,
      `${action}数据源`,
      { confirmButtonText: action, cancelButtonText: '取消', type: 'warning' }
    )
    emit('toggleSource', ds.id, willDisable)
    ElMessage.success(`${sourceLabel} 已${action}`)
  } catch {
    // 用户取消
  }
}

// 格式化
function formatRecords(n: number) {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n || 0)
}
</script>

<template>
  <el-card
    v-loading="loading"
    shadow="never"
    class="ds-mgr-card"
  >
    <template #header>
      <div class="panel-header">
        <div class="header-left">
          <span class="panel-title">
            <el-icon><Connection /></el-icon>
            数据源管理
          </span>
          <el-tooltip
            content="管理参与数据流水线的所有数据源。仅启用且配置了适配器的爬虫源会被实际执行。"
            placement="top"
          >
            <el-icon class="help-icon">
              <QuestionFilled />
            </el-icon>
          </el-tooltip>
        </div>
        <div class="header-right">
          <el-tag
            size="small"
            type="success"
            effect="plain"
            class="mr-2"
          >
            <el-icon :size="11">
              <CircleCheck />
            </el-icon>
            {{ totalEnabled }} 个可用爬虫
          </el-tag>
          <el-tag
            size="small"
            effect="plain"
          >
            {{ dataSources.length }} 总源
          </el-tag>
        </div>
      </div>
    </template>

    <!-- 实时执行状态横幅 (仅在 running 时显示) -->
    <div
      v-if="isRunning"
      class="live-banner"
    >
      <el-icon
        class="rotating"
        :size="14"
      >
        <Loading />
      </el-icon>
      <span class="live-text">
        流水线执行中 — 实时显示每个数据源的状态变化 (SSE 推送)
      </span>
    </div>

    <!-- 可用爬虫源 (可执行) -->
    <div
      v-if="crawlerSources.length"
      class="ds-section"
    >
      <div class="section-label">
        <el-icon :size="12">
          <VideoPlay />
        </el-icon>
        爬虫源 ({{ crawlerSources.length }})
      </div>
      <el-table
        :data="crawlerSources"
        size="small"
        stripe
        :show-overflow-tooltip="true"
        empty-text="暂无爬虫源"
        class="ds-table"
      >
        <el-table-column
          label="数据源"
          min-width="140"
        >
          <template #default="{ row }">
            <div class="ds-name-cell">
              <span class="ds-icon">{{ platformInfo(row).icon }}</span>
              <span class="ds-name">{{ getSourceNameLabel(row.name) }}</span>
              <el-tag
                v-if="row.config?.disabled"
                type="info"
                size="small"
                effect="plain"
                class="ml-1"
              >
                已禁用
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="适配器"
          min-width="120"
        >
          <template #default="{ row }">
            <span :class="['adapter-tag', platformInfo(row).available ? 'available' : 'unavailable']">
              {{ platformInfo(row).label }}
              <el-icon
                v-if="!platformInfo(row).available"
                :size="11"
              ><Warning /></el-icon>
            </span>
          </template>
        </el-table-column>
        <el-table-column
          label="实时状态"
          min-width="120"
        >
          <template #default="{ row }">
            <div :class="['status-cell', statusBadge(row).class]">
              <span
                class="status-dot"
                :style="{ background: statusBadge(row).color }"
              />
              <span class="status-text">{{ statusBadge(row).label }}</span>
              <span
                v-if="row.liveMessage"
                class="status-detail"
              >{{ row.liveMessage }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="关键词 / 目标"
          min-width="120"
        >
          <template #default="{ row }">
            <span class="config-text">{{ row.config?.keyword || '-' }}</span>
            <span class="config-divider">/</span>
            <span class="config-num">{{ row.config?.max_count || 0 }} 条</span>
          </template>
        </el-table-column>
        <el-table-column
          label="权威度"
          min-width="80"
          align="right"
        >
          <template #default="{ row }">
            <span :style="{ color: row.authority_score >= 0.8 ? '#16a34a' : row.authority_score >= 0.6 ? '#f59e0b' : '#dc2626' }">
              {{ (row.authority_score * 100).toFixed(0) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column
          label="记录/有效"
          min-width="100"
          align="right"
        >
          <template #default="{ row }">
            <span class="config-text">{{ formatRecords(row.total_records) }}</span>
            <span class="config-divider">/</span>
            <span :class="['config-text', { 'config-valid': row.valid_records > 0 }]">{{ formatRecords(row.valid_records) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          width="100"
          align="center"
        >
          <template #default="{ row }">
            <el-button
              size="small"
              text
              :type="row.config?.disabled ? 'success' : 'warning'"
              @click="onToggle(row)"
            >
              <el-icon :size="11">
                <VideoPlay v-if="row.config?.disabled" />
                <VideoPause v-else />
              </el-icon>
              {{ row.config?.disabled ? '启用' : '禁用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Phase 3.8.5: 执行详情面板 (当前爬取活动的可读翻译) -->
    <div
      v-if="isRunning && currentActivityDetails"
      class="execution-detail mt-3"
    >
      <div class="detail-header">
        <el-icon
          class="rotating"
          :size="12"
        >
          <Loading />
        </el-icon>
        <span class="detail-title">执行详情 (后端实时翻译)</span>
      </div>
      <div
        v-if="currentActivityDetails.current_activity"
        class="detail-row"
      >
        <span class="detail-label">当前活动:</span>
        <span class="detail-value">{{ currentActivityDetails.current_activity }}</span>
      </div>
      <div
        v-if="currentActivityDetails.recent_samples?.length"
        class="detail-row"
      >
        <span class="detail-label">最近采集:</span>
        <div class="detail-samples">
          <div
            v-for="(s, idx) in currentActivityDetails.recent_samples.slice(0, 3)"
            :key="idx"
            class="sample-line"
          >
            <el-tag
              v-if="s.skill"
              size="small"
              type="warning"
              effect="plain"
            >
              {{ s.skill }}
            </el-tag>
            <span
              v-else
              class="sample-title"
              :title="String(s.title || '')"
            >{{ s.title || s.url || 'unknown' }}</span>
            <span
              v-if="s.company"
              class="sample-company"
            >@ {{ s.company }}</span>
            <span
              v-if="s.source"
              class="sample-source"
            >[{{ s.source }}]</span>
          </div>
        </div>
      </div>
      <div
        v-if="hasSubBreakdown"
        class="detail-row"
      >
        <span class="detail-label">每源进度:</span>
        <div class="detail-breakdown">
          <div
            v-for="(count, name) in currentActivityDetails.sub_breakdown"
            :key="name"
            class="breakdown-pill"
            :class="{
              'breakdown-running': count > 0,
              'breakdown-skipped': count < 0
            }"
          >
            <span class="pill-name">{{ name }}</span>
            <span class="pill-count">{{ count < 0 ? '跳过' : count + ' 条' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 非爬虫源 (API/Manual/Reference/Internal) -->
    <div
      v-if="otherSources.length"
      class="ds-section mt-3"
    >
      <div class="section-label">
        <el-icon :size="12">
          <QuestionFilled />
        </el-icon>
        其他类型数据源 ({{ otherSources.length }})
      </div>
      <el-table
        :data="otherSources"
        size="small"
        stripe
        :show-overflow-tooltip="true"
        empty-text="暂无其他源"
        class="ds-table"
      >
        <el-table-column
          label="数据源"
          min-width="140"
        >
          <template #default="{ row }">
            <div class="ds-name-cell">
              <span class="ds-icon">📦</span>
              <span class="ds-name">{{ getSourceNameLabel(row.name) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="类型"
          min-width="100"
        >
          <template #default="{ row }">
            <el-tag
              size="small"
              effect="plain"
            >
              {{ row.source_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="说明"
          min-width="280"
        >
          <template #default="{ row }">
            <span class="ds-description">
              <template v-if="row.source_type === 'api'">
                通过 API 接口提供数据，不参与爬虫采集，已有 {{ formatRecords(row.total_records) }} 条
              </template>
              <template v-else-if="row.source_type === 'reference'">
                参考数据源，用于校准和参考标准
              </template>
              <template v-else-if="row.source_type === 'internal'">
                内部数据源，由系统内部流程生成
              </template>
              <template v-else-if="row.source_type === 'manual'">
                手动上传数据源，用户已上传 {{ formatRecords(row.total_records) }} 条
              </template>
              <template v-else>
                {{ row.source_type }} 类型数据源
              </template>
            </span>
          </template>
        </el-table-column>
        <el-table-column
          label="记录量"
          min-width="100"
          align="right"
        >
          <template #default="{ row }">
            <span class="config-text">{{ formatRecords(row.total_records) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div
      v-if="!dataSources.length"
      class="empty-tip"
    >
      暂无数据源配置
    </div>
  </el-card>
</template>

<style scoped>
.ds-mgr-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-bottom: 1px solid #e2e8f0;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  font-size: var(--font-size-base);
  color: var(--foreground);
}
.help-icon {
  color: var(--muted-foreground);
  cursor: help;
  font-size: 14px;
}
.help-icon:hover {
  color: var(--primary);
}
.header-right {
  display: flex;
  gap: 6px;
}

/* 实时状态横幅 */
.live-banner {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: linear-gradient(90deg, #dbeafe 0%, #e0e7ff 100%);
  border: 1px solid #93c5fd;
  border-radius: 6px;
  font-size: 12px;
  color: #1d4ed8;
  font-weight: 600;
  margin-bottom: var(--space-3);
}
.rotating {
  animation: rotate 1s linear infinite;
}
@keyframes rotate {
  to { transform: rotate(360deg); }
}

/* 段落 */
.ds-section {
  margin-bottom: var(--space-2);
}
.section-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--muted-foreground);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
  padding-left: 2px;
}

/* 表格 */
.ds-table :deep(.el-table__cell) {
  padding: 6px 0;
}
.ds-name-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ds-icon {
  font-size: 14px;
  width: 20px;
  text-align: center;
}
.ds-name {
  font-weight: 600;
  color: var(--foreground);
}

/* 适配器标签 */
.adapter-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}
.adapter-tag.available {
  background: #dcfce7;
  color: #166534;
}
.adapter-tag.unavailable {
  background: #fee2e2;
  color: #991b1b;
}

/* 状态单元格 */
.status-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--foreground);
}
.status-detail {
  font-size: 10px;
  color: var(--muted-foreground);
  margin-left: 2px;
}
.status-running .status-dot {
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 配置文本 */
.config-text {
  font-size: 11px;
  color: var(--foreground);
  font-family: var(--font-mono, monospace);
}
.config-valid {
  color: #16a34a;
  font-weight: 600;
}
.config-divider {
  color: var(--muted-foreground);
  margin: 0 4px;
  font-size: 10px;
}
.config-num {
  font-size: 11px;
  color: var(--muted-foreground);
}

/* 描述 */
.ds-description {
  font-size: 12px;
  color: var(--muted-foreground);
}

/* 空状态 */
.empty-tip {
  text-align: center;
  padding: var(--space-6);
  color: var(--muted-foreground);
  font-size: 13px;
}

/* Phase 3.8.5: 执行详情面板 */
.execution-detail {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%);
  border: 1px solid #93c5fd;
  border-radius: 8px;
  padding: 12px 16px;
}
.detail-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.detail-title {
  font-size: 12px;
  font-weight: 700;
  color: #1d4ed8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.detail-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
}
.detail-label {
  font-weight: 600;
  color: var(--muted-foreground);
  white-space: nowrap;
  width: 80px;
  flex-shrink: 0;
}
.detail-value {
  color: var(--foreground);
  flex: 1;
  min-width: 0;
}
.detail-samples {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sample-line {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}
.sample-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--foreground);
  flex: 1;
  min-width: 0;
}
.sample-company {
  color: var(--muted-foreground);
  flex-shrink: 0;
  font-size: 10px;
}
.sample-source {
  color: var(--muted-foreground);
  font-size: 10px;
  flex-shrink: 0;
}
.detail-breakdown {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.breakdown-pill {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
}
.breakdown-pill.breakdown-running {
  background: #dbeafe;
  color: #1d4ed8;
}
.breakdown-pill.breakdown-skipped {
  background: #f1f5f9;
  color: #475569;
  opacity: 0.6;
}
.pill-name {
  font-weight: 600;
}
.pill-count {
  font-variant-numeric: tabular-nums;
}

.mr-2 { margin-right: 8px; }
.mt-3 { margin-top: var(--space-3); }
.ml-1 { margin-left: 4px; }
</style>
