<script setup lang="ts">
/**
 * 流水线阶段卡片 — Phase 3.8 增强版
 * 集成实时活动数据：current_activity / recent_samples / sub_breakdown
 * 让 DAG 节点本身就能看到"从采集什么 URL 到提取什么技能"的完整过程
 */
import { ref, computed } from 'vue'
import { CircleCheck, CircleClose, Loading, Connection, Document, MagicStick, Promotion, Share } from '@element-plus/icons-vue'
import { chartColors } from '@/utils/chartTheme'
import { STAGE_LABELS } from '@/stores/pipelineConfig'
import type { LiveActivityEvent } from '@/stores/pipelineRun'

// Phase 3 Plan 02: 阶段描述，供 hover tooltip 引导新用户
// Phase 03 Plan 03 Task 9 (D-13 T6): 阶段描述 — 含作用 + 依赖 + 状态含义三要素
const STAGE_DESCRIPTIONS: Record<string, { role: string; deps: string[]; status_meaning: Record<string, string> }> = {
  crawl: {
    role: '从启用的数据源采集原始 JD 记录，写入 jd_raw 表',
    deps: [],
    status_meaning: {
      pending: '等待前置依赖（无前置）',
      running: '正在从各数据源爬取 JD',
      completed: '本批次所有数据源爬取完成',
      failed: '爬虫失败 — 详见 errors',
      skipped: '被上游跳过',
      cancelled: '用户取消',
    },
  },
  dedup: {
    role: '精确哈希 + SimHash 模糊去重，标记重复记录为 duplicate',
    deps: ['crawl'],
    status_meaning: {
      pending: '等待 crawl 完成',
      running: '精确哈希 + SimHash 模糊比对',
      completed: '去重完成（unique + duplicate 计数已报告）',
      failed: '去重失败 — 检查 Redis 是否可用',
      skipped: '上游失败导致跳过',
      cancelled: '用户取消',
    },
  },
  clean: {
    role: 'HTML 剥离、空白规范化、标题提取（在去重后执行）',
    deps: ['dedup'],
    status_meaning: {
      pending: '等待 dedup 完成',
      running: '清洗 raw 记录（HTML 剥离 + 标题提取）',
      completed: '清洗完成（已设 status=cleaned）',
      failed: '清洗失败 — 单条失败不影响其他记录',
      skipped: '上游失败导致跳过',
      cancelled: '用户取消',
    },
  },
  import: {
    role: 'LLM 技能识别 + 标准化 + 验证，持久化到 PostgreSQL',
    deps: ['clean'],
    status_meaning: {
      pending: '等待 clean 完成',
      running: 'LLM 抽取技能（extract/normalize/persist 子步骤）',
      completed: 'LLM 抽取完成（PG skill_records 已落库）',
      failed: 'LLM 失败 — 重试或检查 API 配额',
      skipped: '上游失败导致跳过',
      cancelled: '用户取消',
    },
  },
  graph_sync: {
    role: '将 PG 数据同步到 Neo4j 图谱（outbox 模式防漂移）',
    deps: ['import'],
    status_meaning: {
      pending: '等待 import 完成',
      running: 'Neo4j 图投影（outbox 模式 + 可选 reconcile）',
      completed: '图谱同步完成（triples 已 MERGE）',
      failed: 'Neo4j 写入失败 — outbox 记录待重试',
      skipped: '上游失败导致跳过',
      cancelled: '用户取消',
    },
  },
  timeseries: {
    role: '聚合技能频率时间序列，供演化分析使用',
    deps: ['graph_sync'],
    status_meaning: {
      pending: '等待 graph_sync 完成',
      running: '正在聚合技能时间窗口',
      completed: '时间序列窗口已生成',
      failed: '聚合失败 — 检查 timeseries_service',
      skipped: '上游失败导致跳过',
      cancelled: '用户取消',
    },
  },
}

export interface StageData {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'cancelled'
  duration_ms: number
  records_processed: number
  records_seen?: number          // Phase 3.8.11
  errors: string[]
  progress: number
  retry_count?: number
  depends_on?: string[]
  started_at?: string | null
  completed_at?: string | null
  errors_count?: number
  // Phase 3.8 实时活动
  current_activity?: string
  recent_samples?: Array<Record<string, unknown>>
  sub_breakdown?: Record<string, number>
  elapsed_ms?: number
}

const props = defineProps<{
  stage: StageData
  liveActivity?: LiveActivityEvent | null
  retrying?: boolean
  blocked?: boolean
}>()

const emit = defineEmits<{
  retry: [stageName: string]
}>()

const STAGE_ICONS: Record<string, unknown> = {
  crawl: Connection,
  dedup: Document,
  clean: MagicStick,
  import: Promotion,
  graph_sync: Share,
}

const statusConfig = computed(() => {
  const colors = chartColors()
  switch (props.stage.status) {
    case 'running':
      return { color: colors.info, label: '运行中', iconType: Loading }
    case 'completed':
      return { color: colors.success, label: '已完成', iconType: CircleCheck }
    case 'failed':
      return { color: colors.danger, label: '失败', iconType: CircleClose }
    case 'skipped':
      return { color: colors.muted, label: '已跳过', iconType: 'minus' }
    case 'pending':
      return { color: colors.muted, label: '待执行', iconType: 'clock' }
    case 'cancelled':
      return { color: colors.warning, label: '已取消', iconType: CircleClose }
    default:
      return { color: colors.muted, label: '等待中', iconType: 'clock' }
  }
})

const stageLabel = computed(() => STAGE_LABELS[props.stage.name] || props.stage.name)
// Phase 03 Plan 03 Task 9 (D-13 T6): 拼装三要素 hover 文本
const stageDesc = computed(() => {
  const desc = STAGE_DESCRIPTIONS[props.stage.name]
  if (!desc) return ''
  const depsLine = desc.deps.length > 0 ? `\n依赖: ${desc.deps.join(', ')}` : '\n依赖: 无'
  const statusLine = `\n当前状态(${props.stage.status}): ${desc.status_meaning[props.stage.status] || '未知'}`
  return desc.role + depsLine + statusLine
})
const StageIcon = computed(() => STAGE_ICONS[props.stage.name] || Connection)

// 实时活动（合并 props.stage 与 liveActivity，优先取 live）
const currentActivity = computed(() => {
  return props.liveActivity?.current_activity || props.stage.current_activity || ''
})

const recentSamples = computed(() => {
  return props.liveActivity?.recent_samples || props.stage.recent_samples || []
})

const subBreakdown = computed(() => {
  return props.liveActivity?.sub_breakdown || props.stage.sub_breakdown || {}
})

// Phase 3.8.2: 增强子项分解 — 包含 disabled (-1) 和 无蜘蛛 (-2) 的源
const breakdownItems = computed(() => {
  const items = Object.entries(subBreakdown.value)
    .filter(([_, v]) => typeof v === 'number' && v !== 0)
    .map(([key, value]) => ({ key, value: Number(value) }))
  return items.sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, 6)
})

const breakdownMax = computed(() => Math.max(1, ...breakdownItems.value.map(i => Math.abs(i.value))))

function breakdownLabel(item: { key: string; value: number }): string {
  if (item.value === -1) return `${item.key} (已禁用)`
  if (item.value === -2) return `${item.key} (无适配器)`
  return item.key
}

function breakdownColor(item: { key: string; value: number }, idx: number): string {
  if (item.value < 0) return '#94a3b8'  // 灰色表示跳过
  return BREAKDOWN_COLORS[idx % BREAKDOWN_COLORS.length]
}

const BREAKDOWN_COLORS = ['#3b82f6', '#8b5cf6', '#06b6d4', '#f59e0b', '#16a34a', '#ec4899', '#6366f1']

// Phase debug (issue): 展开/收起 控制 sub_breakdown + recent_samples 完整显示
const isExpanded = ref(false)
const fullBreakdownItems = computed(() => {
  return Object.entries(subBreakdown.value)
    .filter(([_, v]) => typeof v === 'number')
    .map(([key, value]) => ({ key, value: Number(value) }))
})
const fullRecentSamples = computed(() => recentSamples.value)
const hasMoreDetails = computed(() =>
  fullBreakdownItems.value.length > 6 || fullRecentSamples.value.length > 3
)

const formattedDuration = computed(() => {
  const ms = props.stage.duration_ms
  if (ms <= 0) return '--'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const min = Math.floor(ms / 60000)
  const sec = ((ms % 60000) / 1000).toFixed(0)
  return `${min}m ${sec}s`
})

const errorsExpanded = ref(false)

// Phase 16 残留闭环: 错误去重 + 计数，避免同一错误重复罗列 20 次
const dedupedErrors = computed(() => {
  const counts = new Map<string, number>()
  for (const err of props.stage.errors) {
    counts.set(err, (counts.get(err) || 0) + 1)
  }
  return Array.from(counts.entries()).map(([msg, count]) => ({ msg, count }))
})

// Phase 3.8.11: 显示 "X / Y" (入库 / 抓到) 让用户区分 dedup
const formattedRecords = computed(() => {
  const seen = props.stage.records_seen || 0
  const inserted = props.stage.records_processed || 0
  if (seen > inserted && seen > 0) return `${inserted} / ${seen}`  // X 入库, Y 抓到
  const n = inserted
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
})

// 实际进度：优先 liveActivity.progress，否则 stage.progress
// Phase 16-02 (Fix M3): 防御性 fallback — progress 为 null/undefined 时:
//   - status=completed → 100% (避免"已完成 0%"矛盾显示)
//   - 其他 → 0%
//   - console.warn 提示后端问题 (避免静默掩盖 bug)
const realProgress = computed(() => {
  const raw = props.liveActivity?.progress ?? props.stage.progress
  if (raw === null || raw === undefined) {
    if (props.stage.status === 'completed') {
      console.warn(
        `[PipelineStageCard] stage ${props.stage.name} completed but progress=null — backend bug?`
      )
      return 100
    }
    return 0
  }
  return Math.round(raw * 100)
})
</script>

<template>
  <el-card
    shadow="hover"
    class="stage-card"
    :class="[
      `stage-${stage.status}`,
      { 'has-live-activity': liveActivity?.current_activity }
    ]"
  >
    <!-- 头部：图标 + 名称 + 状态 -->
    <div class="stage-header">
      <div class="stage-status-indicator">
        <span
          class="status-dot"
          :style="{ background: statusConfig.color }"
        />
        <span
          v-if="stage.status === 'running'"
          class="status-pulse"
          :style="{ borderColor: statusConfig.color }"
        />
      </div>
      <el-icon
        class="stage-icon"
        :size="20"
        :style="{ color: statusConfig.color }"
      >
        <component :is="StageIcon" />
      </el-icon>
      <div class="stage-info">
        <el-tooltip
          :content="stageDesc"
          placement="top"
          :disabled="!stageDesc"
          effect="dark"
        >
          <div class="stage-name">
            {{ stageLabel }}
          </div>
        </el-tooltip>
        <div
          class="stage-status-label"
          :style="{ color: statusConfig.color }"
        >
          <el-icon
            v-if="statusConfig.iconType !== 'minus' && statusConfig.iconType !== 'clock'"
            :size="11"
            :class="{ 'rotating': stage.status === 'running' }"
          >
            <component :is="statusConfig.iconType" />
          </el-icon>
          <span v-else>○</span>
          {{ statusConfig.label }}
          <span
            v-if="blocked"
            class="blocked-tag"
          >(阻塞于上游)</span>
          <span
            v-if="stage.retry_count && stage.retry_count > 0"
            class="retry-badge"
          >重试×{{ stage.retry_count }}</span>
        </div>
      </div>
      <el-button
        v-if="stage.status === 'failed' && !blocked"
        size="small"
        type="warning"
        link
        :loading="retrying"
        @click="emit('retry', stage.name)"
      >
        {{ retrying ? '重试中' : '重试' }}
      </el-button>
    </div>

    <!-- 实时活动描述 (核心) -->
    <div
      v-if="currentActivity"
      class="stage-current-activity"
    >
      <el-icon
        v-if="stage.status === 'running'"
        class="rotating"
        :size="12"
        :color="statusConfig.color"
      >
        <Loading />
      </el-icon>
      <el-icon
        v-else
        :size="12"
        :color="statusConfig.color"
      >
        <CircleCheck />
      </el-icon>
      <span class="activity-text">{{ currentActivity }}</span>
    </div>

    <!-- 进度条 -->
    <div
      v-if="stage.status === 'running' || stage.status === 'completed'"
      class="stage-progress"
    >
      <el-progress
        :percentage="realProgress"
        :stroke-width="6"
        :color="statusConfig.color"
        :show-text="false"
      />
      <span class="progress-text">{{ realProgress }}%</span>
    </div>

    <!-- 子项分解 (实时显示每源采集数) -->
    <div
      v-if="breakdownItems.length > 0"
      class="stage-breakdown"
    >
      <div
        v-for="(item, idx) in breakdownItems"
        :key="item.key"
        class="breakdown-row"
        :class="{ 'breakdown-skip': item.value < 0 }"
      >
        <span
          class="breakdown-label"
          :title="breakdownLabel(item)"
        >{{ breakdownLabel(item) }}</span>
        <div class="breakdown-bar-wrap">
          <div
            class="breakdown-bar"
            :style="{
              width: (Math.abs(item.value) / breakdownMax * 100) + '%',
              background: breakdownColor(item, idx),
              opacity: item.value < 0 ? 0.4 : 1,
            }"
          />
        </div>
        <span
          class="breakdown-value"
          :class="{ 'breakdown-skip-text': item.value < 0 }"
        >{{ item.value < 0 ? '跳过' : item.value }}</span>
      </div>

      <!-- Phase debug (issue): 展开/收起按钮 - 查看全部 sub_breakdown -->
      <div
        v-if="hasMoreDetails"
        class="breakdown-toggle"
      >
        <a
          href="javascript:void(0)"
          class="toggle-link"
          @click="isExpanded = !isExpanded"
        >
          {{ isExpanded ? '收起' : `查看全部 (${fullBreakdownItems.length} 项)` }}
        </a>
      </div>

      <!-- 展开后显示完整数据 -->
      <el-dialog
        v-model="isExpanded"
        :title="`${stage.name} 完整详情`"
        width="640"
        append-to-body
      >
        <div class="expanded-section">
          <h4>子项分解 ({{ fullBreakdownItems.length }} 项)</h4>
          <div
            v-for="item in fullBreakdownItems"
            :key="'ex-' + item.key"
            class="expanded-item"
          >
            <span class="expanded-label">{{ item.key }}</span>
            <span class="expanded-value">{{ item.value < 0 ? (item.value === -1 ? '已禁用' : '无适配器') : item.value }}</span>
          </div>
          <h4 v-if="fullRecentSamples.length">
            最近样本 ({{ fullRecentSamples.length }} 条)
          </h4>
          <div
            v-for="(s, si) in fullRecentSamples"
            :key="'sample-' + si"
            class="expanded-sample"
          >
            <div class="sample-title">
              {{ s.title || s.skill || '未命名' }}
            </div>
            <div
              v-if="s.company || s.source"
              class="sample-meta"
            >
              {{ s.company }} {{ s.source ? `· ${s.source}` : '' }}
            </div>
            <a
              v-if="s.url"
              :href="(s.url as string)"
              target="_blank"
              class="sample-url"
            >{{ s.url }}</a>
          </div>
        </div>
      </el-dialog>
    </div>

    <!-- 最近数据样本 -->
    <div
      v-if="recentSamples.length > 0"
      class="stage-samples"
    >
      <div class="samples-title">
        最近样本:
      </div>
      <div class="samples-list">
        <div
          v-for="(s, si) in recentSamples.slice(0, 3)"
          :key="si"
          class="sample-chip"
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
          >{{ s.title || s.url || JSON.stringify(s).slice(0, 40) }}</span>
          <span
            v-if="s.source"
            class="sample-source"
          >{{ s.source }}</span>
        </div>
      </div>
    </div>

    <!-- 基础指标 -->
    <div class="stage-metrics">
      <div class="metric">
        <span class="metric-label">耗时</span>
        <span class="metric-value">{{ formattedDuration }}</span>
      </div>
      <div class="metric">
        <span class="metric-label">处理量</span>
        <!-- Phase debug (issue): 加 tooltip 解释"原始 vs 新增" -->
        <el-tooltip
          v-if="stage.name === 'crawl'"
          content="原始数据 = 本次爬取的全部条目；新增 = 实际入库的新记录 (其余为已存在的重复内容)"
          placement="top"
        >
          <span class="metric-value metric-value-link">{{ formattedRecords }}</span>
        </el-tooltip>
        <span
          v-else
          class="metric-value"
        >{{ formattedRecords }}</span>
      </div>
      <div
        v-if="(stage.errors_count ?? stage.errors.length) > 0"
        class="metric metric-error"
      >
        <span class="metric-label">错误</span>
        <span
          class="metric-value"
          :style="{ color: chartColors().danger }"
        >{{ stage.errors_count ?? stage.errors.length }}</span>
      </div>
    </div>

    <!-- Phase 3.8.8: 错误按需展开 (不挤爆卡片) -->
    <div
      v-if="stage.status === 'failed' && stage.errors.length > 0"
      class="stage-error-detail"
    >
      <el-alert
        type="error"
        :closable="false"
        effect="light"
      >
        <template #title>
          <div class="error-summary">
            <span class="error-count-badge">{{ stage.errors.length }} 个错误</span>
            <a
              href="javascript:void(0)"
              class="error-toggle"
              @click="errorsExpanded = !errorsExpanded"
            >{{ errorsExpanded ? '收起' : '展开详情' }}</a>
          </div>
          <div
            v-if="errorsExpanded"
            class="error-list"
          >
            <div
              v-for="(item, i) in dedupedErrors"
              :key="i"
              class="error-line"
            >
              {{ item.msg }}<span
                v-if="item.count > 1"
                class="error-repeat-badge"
              > ×{{ item.count }}</span>
            </div>
          </div>
        </template>
      </el-alert>
    </div>
  </el-card>
</template>

<style scoped>
.stage-card {
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
  min-width: 200px;
  max-width: 260px;
}
.stage-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.stage-running {
  border-left: 3px solid var(--info);
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
}
.stage-completed {
  border-left: 3px solid var(--success);
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
}
.stage-failed {
  border: 2px solid var(--destructive);
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  animation: failed-pulse 2s ease-in-out infinite;
}
.stage-pending {
  border-left: 3px solid var(--muted-foreground);
  opacity: 0.85;
}
.stage-skipped {
  border-left: 3px solid var(--muted-foreground, #d1d5db);
  opacity: 0.5;
}
.stage-cancelled {
  border-left: 3px solid var(--warning);
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
}
@keyframes failed-pulse {
  0%, 100% { box-shadow: 0 0 12px color-mix(in srgb, var(--destructive) 30%, transparent); }
  50% { box-shadow: 0 0 20px color-mix(in srgb, var(--destructive) 50%, transparent); }
}

.stage-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.stage-icon {
  flex-shrink: 0;
}
.stage-status-indicator {
  position: relative;
  width: 10px;
  height: 10px;
  flex-shrink: 0;
}
.status-dot {
  display: block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  position: relative;
  z-index: 1;
}
.status-pulse {
  position: absolute;
  top: -5px;
  left: -5px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid;
  animation: pulse-ring 1.5s ease-out infinite;
}
@keyframes pulse-ring {
  0% { transform: scale(0.8); opacity: 1; }
  100% { transform: scale(1.6); opacity: 0; }
}
.stage-info {
  flex: 1;
  min-width: 0;
}
.stage-name {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--foreground);
  letter-spacing: var(--tracking-tight);
  white-space: nowrap;
}
.stage-status-label {
  font-size: 10px;
  font-weight: 500;
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 3px;
}
.rotating {
  animation: rotate 1s linear infinite;
}
@keyframes rotate {
  to { transform: rotate(360deg); }
}
.retry-badge {
  font-size: 9px;
  padding: 1px 4px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--warning) 15%, transparent);
  color: var(--warning);
  font-weight: 600;
  margin-left: 4px;
}
.blocked-tag {
  font-size: 10px;
  color: var(--muted-foreground);
  font-style: italic;
  margin-left: 4px;
}

/* 实时活动描述 */
.stage-current-activity {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  margin-bottom: 6px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 4px;
  font-size: 11px;
  line-height: 1.4;
}
.activity-text {
  color: var(--foreground);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

/* 进度条 */
.stage-progress {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 6px;
}
.progress-text {
  font-size: 10px;
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  font-weight: 600;
}

/* 子项分解条形图 */
.stage-breakdown {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 6px;
  padding: 4px 6px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 4px;
}
.breakdown-row {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
}
.breakdown-label {
  width: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--muted-foreground);
  font-size: 9px;
}
.breakdown-bar-wrap {
  flex: 1;
  height: 6px;
  background: var(--muted);
  border-radius: 3px;
  overflow: hidden;
}
.breakdown-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}
.breakdown-value {
  font-weight: 600;
  min-width: 18px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--foreground);
}
.breakdown-skip .breakdown-label {
  color: var(--muted-foreground);
  text-decoration: line-through;
  opacity: 0.6;
}
.breakdown-skip-text {
  color: var(--muted-foreground);
  font-size: 10px;
  font-style: italic;
}

/* 数据样本 */
.stage-samples {
  margin-bottom: 6px;
  padding: 4px 6px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 4px;
}
.samples-title {
  font-size: 9px;
  color: var(--muted-foreground);
  margin-bottom: 2px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  font-weight: 600;
}
.samples-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sample-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
}
.sample-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--foreground);
  flex: 1;
  min-width: 0;
}
.sample-source {
  font-size: 9px;
  color: var(--muted-foreground);
  flex-shrink: 0;
}

/* 基础指标 */
.stage-metrics {
  display: flex;
  gap: var(--space-3);
  padding-top: 6px;
  border-top: 1px solid var(--border);
}
.metric {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.metric-label {
  font-size: 9px;
  color: var(--muted-foreground);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.metric-value {
  font-size: 11px;
  font-weight: 600;
  color: var(--foreground);
  font-variant-numeric: tabular-nums;
}
.metric-error .metric-value {
  color: var(--destructive);
}

/* 错误详情 */
.stage-error-detail {
  margin-top: 6px;
}
.error-list {
  margin-top: 6px;
  max-height: 120px;
  overflow-y: auto;
}
.error-line {
  font-size: 11px;
  line-height: 1.6;
  color: var(--destructive);
  word-break: break-all;
}
.error-repeat-badge {
  display: inline-block;
  margin-left: 4px;
  padding: 0 4px;
  font-size: 10px;
  font-weight: 700;
  background: color-mix(in srgb, var(--destructive) 15%, transparent);
  border-radius: 3px;
  color: var(--destructive);
}
</style>
