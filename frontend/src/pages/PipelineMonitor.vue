<script setup lang="ts">
/**
 * 数据流水线监控页 — Plan 03 Task 8 拆子组件后瘦身 < 600 行。
 * 仅保留顶层布局 + KPI 卡片 + DAG 区 + 子组件挂载点 + 闭环验证编排。
 */
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled, Refresh, Setting, Timer, VideoPlay, RefreshRight } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import BusinessBanner from '@/components/BusinessBanner.vue'
import { ALL_STAGE_NAMES, STAGE_LABELS } from '@/stores/pipelineConfig'
import PipelineDag from '@/components/PipelineDag.vue'
import DataSourceManager from '@/components/DataSourceManager.vue'
import PipelineStatusHero from '@/components/PipelineStatusHero.vue'
import PipelineKpiCards from '@/components/PipelineKpiCards.vue'
import PipelineGlossary from '@/components/PipelineGlossary.vue'
import TriggerDialog from '@/components/pipeline/TriggerDialog.vue'
import ScheduleForm from '@/components/pipeline/ScheduleForm.vue'
import ScheduleList from '@/components/pipeline/ScheduleList.vue'
import ConfigDialog from '@/components/pipeline/ConfigDialog.vue'
import VerifyLogPanel from '@/components/pipeline/VerifyLogPanel.vue'
import StuckAlert from '@/components/pipeline/StuckAlert.vue'
import QualityPanel from '@/components/pipeline/QualityPanel.vue'
import RunHistory from '@/components/pipeline/RunHistory.vue'
import { usePipelineMonitor } from '@/composables/usePipelineMonitor'
import { useTriggerPipeline } from '@/composables/useTriggerPipeline'
import { useSchedules } from '@/composables/useSchedules'
import { useVerifyLog } from '@/composables/useVerifyLog'
import { getSourceNameLabel } from '@/composables/useDataSourceCharts'
import { useDataSourceStore } from '@/stores/datasource'

const datasourceStore = useDataSourceStore()

const {
  pipeline,
  isAdmin,
  configSaving,
  autoRefresh,
  refreshInterval,
  lastRefresh,
  loadAll,
  toggleAutoRefresh,
  startAutoRefresh,
  sseConnected,
  sseMode,
  kpiCards,
  stageSummary,
  isStuck,
  stuckReason,
  timelineStages,
  blockedStages,
  configDialogVisible,
  openConfigDialog,
  handleSaveConfig,
  pendingReviewCount,
  liveActivity,
} = usePipelineMonitor()

const { actionLogs, isVerifying, verifyState, appendLog, clearLogs } = useVerifyLog()

const {
  actionLoading,
  retryingStages,
  selectedStages,
  selectedSources,
  triggerDialogVisible,
  triggerRunType,
  openTriggerDialog,
  trigger,
  handleRetryStage,
  handleResume,
  cancelRun,
  forceAdvance,
  forceReset,
} = useTriggerPipeline({
  onAfterTrigger: () => { refreshInterval.value = 5; startAutoRefresh() },
  onAfterMutation: loadAll,
})

// D8: 触发/调度对话框可选数据源 —— 全部 active 的爬虫源（有 config.platform 的）
// 用 pipeline store 的 dataSources（loadAll 已加载），而非 datasource store
const triggerSourceOptions = computed(() =>
  (pipeline.dataSources || [])
    .filter(s => s.status === 'active' && s.config?.platform)
    .map(s => ({
      name: s.name,
      label: getSourceNameLabel(s.name),
    })),
)

const {
  scheduleLoading,
  scheduleDialogVisible,
  scheduleForm,
  openScheduleDialog,
  handleCreateSchedule,
  handleDeleteSchedule,
  handleTriggerSchedule,
  handleToggleSchedule,
} = useSchedules({ onAfterTrigger: loadAll })

// ── 术语词典对话框 ──
const glossaryVisible = ref(false)

// ── 触发后无需 verifyState — triggerPipeline 内部已 fetchStatus/fetchStages ──
async function handleTriggerWithVerify() {
  pipeline.resetLiveActivity()
  const ok = await trigger(selectedStages.value, triggerRunType.value, selectedSources.value)
  if (ok) {
    triggerDialogVisible.value = false
  } else {
    appendLog({
      action: '触发流水线',
      apiEndpoint: 'POST /pipeline/trigger',
      result: 'failed',
      resultMessage: '触发失败',
      verifiedBy: '已显示错误',
      durationMs: 0,
    })
  }
  actionLoading.value = false
}

/** 包装取消运行: 取消后验证状态 */
async function handleCancelWithVerify() {
  const runId = pipeline.pipelineStatus?.current_run?.id
  if (!runId) {
    ElMessage.warning('没有正在运行的流水线')
    return
  }
  const startTime = Date.now()
  const beforeStatus = pipeline.pipelineStatus?.current_run?.status
  const ok = await cancelRun(runId)
  if (ok) {
    await loadAll()
    await verifyState(
      '取消运行',
      `POST /pipeline/runs/${runId.slice(0, 8)}/cancel`,
      'success',
      `Cancelled in ${Date.now() - startTime}ms`,
      Date.now() - startTime,
      async () => {
        await pipeline.fetchStatus()
        await pipeline.fetchStages()
        const afterStatus = pipeline.pipelineStatus?.current_run?.status
        const isRunning = pipeline.pipelineStatus?.is_running
        return {
          verified: isRunning === false || afterStatus === 'cancelled',
          verifiedBy: `before=${beforeStatus}, after=${afterStatus}, is_running=${isRunning}`,
          verifiedValue: { before: beforeStatus, after: afterStatus, is_running: isRunning },
        }
      },
    )
  }
}

/** 强制推进卡死 run (带验证) */
async function onForceAdvance() {
  const runId = pipeline.pipelineStatus?.current_run?.id
  if (!runId) {
    ElMessage.warning('没有正在运行的流水线')
    return
  }
  const startTime = Date.now()
  const ok = await forceAdvance(runId)
  if (ok) {
    await verifyState(
      '强制推进',
      `POST /pipeline/runs/${runId.slice(0, 8)}/force-advance`,
      'success',
      `Advanced in ${Date.now() - startTime}ms`,
      Date.now() - startTime,
      async () => {
        await pipeline.fetchStatus()
        await pipeline.fetchStages()
        const stages = pipeline.stages.filter(s => s.status !== 'skipped')
        const stillPending = stages.filter(s => s.status === 'pending').length
        const nowRunning = stages.filter(s => s.status === 'running').length
        return {
          verified: stillPending === 0 || nowRunning > 0,
          verifiedBy: `待执行=${stillPending}, 运行中=${nowRunning}`,
          verifiedValue: { pending: stillPending, running: nowRunning },
        }
      },
    )
  } else {
    ElMessage.error('强制推进失败, 请查看浏览器控制台')
  }
}

/** 强制重置卡死 run (带验证) */
async function onForceReset() {
  const runId = pipeline.pipelineStatus?.current_run?.id
  if (!runId) {
    ElMessage.warning('没有正在运行的流水线')
    return
  }
  const startTime = Date.now()
  const ok = await forceReset(runId)
  if (ok) {
    await verifyState(
      '强制重置',
      `POST /pipeline/runs/${runId.slice(0, 8)}/force-reset`,
      'success',
      `Reset in ${Date.now() - startTime}ms`,
      Date.now() - startTime,
      async () => {
        await pipeline.fetchStatus()
        await pipeline.fetchStages()
        return {
          verified: !pipeline.pipelineStatus?.is_running,
          verifiedBy: `is_running = ${pipeline.pipelineStatus?.is_running} (期望 false)`,
          verifiedValue: { is_running: pipeline.pipelineStatus?.is_running },
        }
      },
    )
  } else {
    ElMessage.error('强制重置失败, 请查看浏览器控制台')
  }
}

/** 手动触发验证 - 重新检查当前所有状态 */
async function verifyNow() {
  isVerifying.value = true
  try {
    await Promise.all([
      pipeline.fetchStatus(),
      pipeline.fetchStages(),
      pipeline.fetchDataQuality(),
      pipeline.fetchDataSources(),
    ])
    const ps = pipeline.pipelineStatus
    const stages = pipeline.stages
    const running = stages.filter(s => s.status === 'running').length
    const completed = stages.filter(s => s.status === 'completed').length
    const failed = stages.filter(s => s.status === 'failed').length
    const cancelled = stages.filter(s => s.status === 'cancelled').length
    const summary = `KPI=${ps?.success_rate ? (ps.success_rate * 100).toFixed(1) + '%' : '--'} | 数据源=${ps?.active_data_sources ?? '--'} | 阶段: ${running}运行/${completed}完成/${failed}失败/${cancelled}取消`
    appendLog({
      action: '手动验证当前状态',
      apiEndpoint: 'GET /pipeline/{status,stages}',
      result: 'success',
      resultMessage: summary,
      verifiedBy: summary,
      durationMs: 0,
    })
    ElMessage.success('状态已刷新并验证')
  } finally {
    isVerifying.value = false
  }
}

/** 切换数据源启用/禁用 (真实调用 PUT /datasources/{id} 持久化) */
async function onToggleSource(sourceId: string, willDisable: boolean) {
  const startTime = Date.now()
  const source = pipeline.dataSources.find(s => s.id === sourceId)
  if (!source) return
  try {
    const newCfg = { ...(source.config || {}), disabled: willDisable }
    const updated = await datasourceStore.updateSource(sourceId, { config: newCfg })
    if (!updated) throw new Error(datasourceStore.error || '数据源状态持久化失败')
    const idx = pipeline.dataSources.findIndex(s => s.id === sourceId)
    if (idx >= 0) pipeline.dataSources[idx] = { ...source, config: updated.config ?? newCfg }
    const persistedDisabled = updated.config?.disabled ?? willDisable
    await verifyState(
      `${willDisable ? '禁用' : '启用'}数据源 ${getSourceNameLabel(source.name)}`,
      `PUT /datasources/${sourceId.slice(0, 8)}`,
      'success',
      `${getSourceNameLabel(source.name)} ${willDisable ? '已禁用' : '已启用'}（后端已持久化）`,
      Date.now() - startTime,
      async () => ({
        verified: persistedDisabled === willDisable,
        verifiedBy: `后端返回 ${getSourceNameLabel(source.name)}.config.disabled = ${persistedDisabled} (期望 ${willDisable})`,
        verifiedValue: { source: getSourceNameLabel(source.name), disabled: persistedDisabled },
      }),
    )
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}
</script>

<template>
  <MainLayout>
    <div class="pipeline-page animate-fade-in">
      <BusinessBanner
        type="success"
        title="数据流水线监控"
        description="看数据从爬虫采集到写入图谱的全过程：每个阶段独立降级，失败不阻塞下一步。数据源质量越高，最终岗位/技能的信任度评分也越高。"
        meta="后端: <code>/pipeline/*</code> · 数据源: <code>pipeline_runs</code> 表 · SSE 实时推送"
      />

      <!-- 页面头部 -->
      <div class="page-header">
        <div>
          <h2>数据流水线监控</h2>
          <p class="page-desc">
            ETL DAG 全链路：爬虫采集 → 去重 → 清洗 → 入库 → 图谱构建
            <el-tag
              v-if="sseConnected"
              size="small"
              type="success"
              effect="plain"
              class="ml-2"
            >
              SSE 实时
            </el-tag>
            <el-tag
              v-else-if="sseMode === 'polling'"
              size="small"
              type="info"
              effect="plain"
              class="ml-2"
            >
              轮询模式
            </el-tag>
            <el-tag
              v-else
              size="small"
              type="warning"
              effect="plain"
              class="ml-2"
            >
              连接中断
            </el-tag>
          </p>
        </div>
        <!-- Plan 02: SSE 断开时用户可见提示 -->
        <el-alert
          v-if="!sseConnected"
          type="warning"
          :closable="false"
          show-icon
          class="mb-4"
          title="实时推送已断开"
          :description="sseMode === 'polling' ? '已自动切换为轮询模式，数据每 10 秒刷新一次' : '正在尝试重新连接...'"
        />
        <div class="header-actions">
          <span
            v-if="lastRefresh"
            class="last-refresh"
          >最近刷新: {{ lastRefresh }}</span>
          <el-button
            size="small"
            :icon="QuestionFilled"
            @click="glossaryVisible = true"
          >
            新手指引
          </el-button>
          <el-button
            size="small"
            :icon="Refresh"
            :loading="isVerifying"
            @click="verifyNow"
          >
            校验状态
          </el-button>
          <el-switch
            v-model="autoRefresh"
            active-text="自动刷新"
            size="small"
            @change="toggleAutoRefresh"
          />
          <!-- LOOP-08: admin-only management controls -->
          <template v-if="isAdmin">
            <el-button
              size="small"
              type="primary"
              :icon="VideoPlay"
              :loading="actionLoading"
              :disabled="pipeline.pipelineStatus?.is_running"
              @click="openTriggerDialog"
            >
              触发流水线
            </el-button>
            <el-button
              v-if="pipeline.pipelineStatus?.recent_failed_run && !pipeline.pipelineStatus?.is_running"
              size="small"
              type="warning"
              :loading="actionLoading"
              @click="handleResume"
            >
              断点续跑
            </el-button>
            <el-button
              v-if="pipeline.pipelineStatus?.current_run?.status === 'running'"
              size="small"
              type="danger"
              plain
              :loading="actionLoading"
              @click="handleCancelWithVerify"
            >
              取消运行
            </el-button>
            <el-button
              size="small"
              :icon="Timer"
              :loading="scheduleLoading"
              @click="openScheduleDialog"
            >
              定时调度
            </el-button>
            <el-button
              size="small"
              :icon="Setting"
              @click="openConfigDialog"
            >
              配置
            </el-button>
          </template>
          <el-button
            size="small"
            :icon="RefreshRight"
            @click="loadAll"
          >
            刷新
          </el-button>
        </div>
      </div>

      <!-- 状态摘要 Hero 卡片 -->
      <PipelineStatusHero
        :is-running="pipeline.pipelineStatus?.is_running ?? false"
        :summary="stageSummary"
      />

      <!-- 4 个 KPI 卡片 -->
      <PipelineKpiCards :cards="kpiCards" />

      <!-- 数据审核闭环: 待审核提示 -->
      <el-alert
        v-if="pendingReviewCount > 0"
        type="warning"
        :closable="true"
        show-icon
        class="mb-4"
      >
        <template #title>
          <span>📋 <strong>{{ pendingReviewCount }}</strong> 条新抽取数据待审核（岗位/技能）——审核通过后将自动纳入图谱</span>
        </template>
      </el-alert>

      <!-- 卡死检测横幅 + 强制操作 -->
      <StuckAlert
        v-if="isStuck"
        :reason="stuckReason"
        :loading="actionLoading"
        @force-advance="onForceAdvance"
        @force-reset="onForceReset"
      />

      <!-- 流水线 DAG 时间线视图 -->
      <PipelineDag
        :timeline-stages="timelineStages"
        :blocked-stages="blockedStages"
        :retrying-stages="retryingStages"
        :loading="pipeline.loading"
        :is-running="pipeline.pipelineStatus?.is_running ?? false"
        :action-loading="actionLoading"
        :live-activity="liveActivity"
        @retry="handleRetryStage"
      />

      <!-- 闭环验证日志面板 -->
      <VerifyLogPanel
        :logs="actionLogs"
        :is-verifying="isVerifying"
        @clear="clearLogs"
      />

      <!-- 底部：数据源面板 + 数据质量监控 -->
      <el-row :gutter="16">
        <el-col
          :lg="14"
          :md="24"
          class="mb-4"
        >
          <DataSourceManager
            :data-sources="pipeline.dataSources"
            :live-activity="liveActivity"
            :is-running="pipeline.pipelineStatus?.is_running ?? false"
            :current-stage-progress="0"
            :loading="pipeline.loading"
            @toggle-source="onToggleSource"
          />
        </el-col>
        <el-col
          :lg="10"
          :md="24"
          class="mb-4"
        >
          <QualityPanel
            :data-quality="pipeline.dataQuality"
            :loading="pipeline.loading"
          />
        </el-col>
      </el-row>

      <!-- 定时调度列表 -->
      <ScheduleList
        :schedules="pipeline.schedules"
        :is-admin="isAdmin"
        :loading="pipeline.loading"
        @toggle="handleToggleSchedule"
        @trigger="handleTriggerSchedule"
        @delete="handleDeleteSchedule"
        @add="openScheduleDialog"
      />

      <!-- 运行历史列表 -->
      <RunHistory
        :runs="pipeline.runs"
        :loading="pipeline.loading"
        :is-admin="isAdmin"
        @resume="handleResume"
        @cancel="handleCancelWithVerify"
      />

      <!-- ── 触发流水线弹窗 ── -->
      <TriggerDialog
        v-model="triggerDialogVisible"
        :run-type="triggerRunType"
        :selected-stages="selectedStages"
        :available-stages="ALL_STAGE_NAMES"
        :stage-labels="STAGE_LABELS"
        :selected-sources="selectedSources"
        :available-sources="triggerSourceOptions"
        :loading="actionLoading"
        @update:run-type="triggerRunType = $event"
        @update:selected-stages="selectedStages = $event"
        @update:selected-sources="selectedSources = $event"
        @submit="handleTriggerWithVerify"
      />

      <!-- ── 定时调度弹窗 ── -->
      <ScheduleForm
        v-model="scheduleDialogVisible"
        :form="scheduleForm"
        :available-sources="triggerSourceOptions"
        :loading="scheduleLoading"
        @update:form="scheduleForm = $event"
        @submit="handleCreateSchedule"
      />

      <!-- ── 配置弹窗 ── -->
      <ConfigDialog
        v-model="configDialogVisible"
        :config="pipeline.config"
        :saving="configSaving"
        @save="handleSaveConfig"
      />
    </div>

    <!-- 术语词典 (新手指引) -->
    <PipelineGlossary v-model="glossaryVisible" />
  </MainLayout>
</template>

<style scoped>
.pipeline-page {
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-6);
  flex-wrap: wrap;
  gap: var(--space-3);
}
.page-header h2 {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  color: var(--foreground);
  margin: 0 0 var(--space-1);
  letter-spacing: var(--tracking-tight);
}
.page-desc {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.last-refresh {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
.mb-4 { margin-bottom: var(--space-4); }
.ml-2 { margin-left: var(--space-2); }
@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .header-actions { width: 100%; justify-content: flex-start; }
}
</style>
