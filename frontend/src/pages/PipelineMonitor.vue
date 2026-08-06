<script setup lang="ts">
/**
 * 数据流水线监控页 — Phase 3.8 增强版
 * 展示 ETL DAG + 实时活动数据 (集成到 DAG 内部) + 闭环验证
 * 支持：阶段选择触发、实时SSE进度、失败重试/断点续跑、定时调度、配置调整
 */
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, Connection, Loading, Lock, QuestionFilled, RefreshRight, Setting, Timer, VideoPlay, Check, Refresh } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import BusinessBanner from '@/components/BusinessBanner.vue'
import { ALL_STAGE_NAMES, STAGE_LABELS } from '@/stores/pipeline'
import PipelineDag from '@/components/PipelineDag.vue'
import DataSourceManager from '@/components/DataSourceManager.vue'
import PipelineQualityPanel from '@/components/PipelineQualityPanel.vue'
import PipelineStatusHero from '@/components/PipelineStatusHero.vue'
import PipelineKpiCards from '@/components/PipelineKpiCards.vue'
import PipelineGlossary from '@/components/PipelineGlossary.vue'
import { usePipelineMonitor } from '@/composables/usePipelineMonitor'
import { getSourceNameLabel } from '@/composables/useDataSourceCharts'
import { useDataSourceStore } from '@/stores/datasource'

const datasourceStore = useDataSourceStore()

const {
  pipeline,
  actionLoading,
  scheduleLoading,
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
  retryingStages,
  handleRetryStage,
  handleResume,
  selectedStages,
  triggerDialogVisible,
  triggerRunType,
  openTriggerDialog,
  scheduleDialogVisible,
  scheduleForm,
  openScheduleDialog,
  handleCreateSchedule,
  handleDeleteSchedule,
  handleTriggerSchedule,
  handleToggleSchedule,
  configDialogVisible,
  openConfigDialog,
  handleSaveConfig,
  qualityTrendOption,
  qualityTrendDir,
  isAdmin,
  liveActivity,
  pendingReviewCount,
} = usePipelineMonitor()

// ── Phase 3.8 闭环验证系统 ──
// 每个操作记录: action, result, verification, timestamp
interface ActionLog {
  id: string
  timestamp: number
  action: string           // 操作名 (e.g. "触发流水线 (全量)")
  apiEndpoint: string      // 触发的 API
  result: 'success' | 'failed' | 'pending'
  resultMessage: string    // 后端返回消息
  verifiedBy: string       // 如何验证 (e.g. "current_run.status = running")
  verifiedValue?: unknown  // 实际验证值
  durationMs: number        // API 调用耗时
}
// Phase 3.8.2 FIX: 闭环验证日志持久化到 localStorage (解决刷新后数据丢失)
const VERIFY_LOG_KEY = 'starmap_pipeline_verify_log_v1'
const VERIFY_LOG_MAX = 30
const actionLogs = ref<ActionLog[]>([])
const isVerifying = ref(false)
// Phase 3.8.5: 术语词典对话框
const glossaryVisible = ref(false)

// 启动时从 localStorage 加载历史日志
try {
  const saved = localStorage.getItem(VERIFY_LOG_KEY)
  if (saved) {
    const parsed = JSON.parse(saved)
    if (Array.isArray(parsed)) {
      actionLogs.value = parsed.slice(0, VERIFY_LOG_MAX)
    }
  }
} catch (e) {
  console.error('加载验证日志失败:', e)
}

function persistLogs() {
  try {
    localStorage.setItem(VERIFY_LOG_KEY, JSON.stringify(actionLogs.value.slice(0, VERIFY_LOG_MAX)))
  } catch (e) {
    console.error('保存验证日志失败:', e)
  }
}

function appendLog(log: Omit<ActionLog, 'id' | 'timestamp'>) {
  const entry: ActionLog = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    timestamp: Date.now(),
    ...log,
  }
  actionLogs.value.unshift(entry)
  if (actionLogs.value.length > VERIFY_LOG_MAX) {
    actionLogs.value = actionLogs.value.slice(0, VERIFY_LOG_MAX)
  }
  persistLogs()
}

function clearLogs() {
  actionLogs.value = []
  persistLogs()
  ElMessage.success('验证日志已清空')
}

function logTime(ts: number) {
  // Phase 7: defensive against invalid timestamps (NaN, undefined, negative)
  if (typeof ts !== 'number' || !Number.isFinite(ts) || ts < 0) return '--:--:--'
  return new Date(ts).toLocaleTimeString('zh-CN', { hour12: false })
}

/** Phase 3.8 核心: 每次操作后自动验证 */
async function verifyState(
  action: string,
  apiEndpoint: string,
  apiResult: 'success' | 'failed' | 'pending',
  resultMessage: string,
  durationMs: number,
  expectFn: () => Promise<{ verified: boolean; verifiedBy: string; verifiedValue?: unknown }>,
) {
  // 立即记录 API 调用结果
  appendLog({
    action, apiEndpoint, result: apiResult, resultMessage, durationMs,
    verifiedBy: '验证中...', verifiedValue: undefined,
  })
  // Phase 3.8.1 FIX: 先 sleep 800ms 等待 store 实际更新 (避免 race condition)
  await new Promise(resolve => setTimeout(resolve, 800))
  // 异步执行验证
  isVerifying.value = true
  try {
    const { verified, verifiedBy, verifiedValue } = await expectFn()
    // 更新最新日志
    actionLogs.value[0].verifiedBy = verifiedBy
    actionLogs.value[0].verifiedValue = verifiedValue
    persistLogs()  // Phase 3.8.2: 验证结果立即持久化
    if (!verified) {
      actionLogs.value[0].result = 'failed'
      ElMessage.warning(`验证未通过: ${verifiedBy}`)
    }
  } catch (e) {
    actionLogs.value[0].verifiedBy = `验证异常: ${e instanceof Error ? e.message : '未知'}`
  } finally {
    isVerifying.value = false
  }
}

/** Pony 3.8.9: 触发后无需 verifyState — triggerPipeline 内部已 fetchStatus/fetchStages */
async function handleTriggerWithVerify() {
  try {
    pipeline.resetLiveActivity()
    await pipeline.triggerPipeline(triggerRunType.value, selectedStages.value)
    triggerDialogVisible.value = false
    const runTypeLabel = triggerRunType.value === 'full' ? '全量' : '增量'
    const stageCount = selectedStages.value.length
    ElMessage.success(`流水线已触发（${runTypeLabel}，${stageCount} 个阶段）`)
    refreshInterval.value = 5
    startAutoRefresh()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '触发失败'
    ElMessage.error(`触发失败：${msg}`)
    appendLog({
      action: '触发流水线',
      apiEndpoint: 'POST /pipeline/trigger',
      result: 'failed',
      resultMessage: msg,
      verifiedBy: '已显示错误',
      durationMs: 0,
    })
  } finally {
    actionLoading.value = false
  }
}

/** 包装 handleCancelRun: 取消后验证状态 */
async function handleCancelWithVerify() {
  const runId = pipeline.pipelineStatus?.current_run?.id
  if (!runId) {
    ElMessage.warning('没有正在运行的流水线')
    return
  }
  const startTime = Date.now()
  const beforeStatus = pipeline.pipelineStatus?.current_run?.status
  try {
    await ElMessageBox.confirm(
      '确认取消当前正在运行的流水线？此操作不可撤销。',
      '取消流水线',
      { confirmButtonText: '确认取消', cancelButtonText: '不取消', type: 'warning' }
    )
    actionLoading.value = true
      const ok = await pipeline.cancelRun(runId)
      if (ok) {
        await loadAll()
        ElMessage.success('流水线已取消，所有运行中阶段已停止')
        const duration = Date.now() - startTime
        await verifyState(
          '取消运行',
          `POST /pipeline/runs/${runId.slice(0, 8)}/cancel`,
          'success',
          `Cancelled in ${duration}ms`,
          duration,
          async () => {
            // Phase 3.8.1: 强制重新拉取最新状态 (避免 race condition)
            await pipeline.fetchStatus()
            await pipeline.fetchStages()
            const afterStatus = pipeline.pipelineStatus?.current_run?.status
            const isRunning = pipeline.pipelineStatus?.is_running
            const verified = isRunning === false || afterStatus === 'cancelled'
            return {
              verified,
              verifiedBy: `before=${beforeStatus}, after=${afterStatus}, is_running=${isRunning}`,
              verifiedValue: { before: beforeStatus, after: afterStatus, is_running: isRunning },
            }
          },
        )
    } else {
      // 检查是否已经处于终态 (用户重复点击)
      const isTerminal = ['cancelled', 'completed', 'failed'].includes(
        pipeline.pipelineStatus?.current_run?.status || ''
      )
      if (isTerminal) {
        const cur = pipeline.pipelineStatus?.current_run?.status
        ElMessage.info(`该流水线已结束（${cur}），无需再次取消`)
        appendLog({
          action: '取消运行',
          apiEndpoint: `POST /pipeline/runs/${runId.slice(0, 8)}/cancel`,
          result: 'success',
          resultMessage: `已是 ${cur} 状态`,
          verifiedBy: '已是终态',
          durationMs: 0,
        })
      } else {
        ElMessage.error('取消失败，请查看浏览器控制台')
        appendLog({
          action: '取消运行',
          apiEndpoint: `POST /pipeline/runs/${runId.slice(0, 8)}/cancel`,
          result: 'failed',
          resultMessage: '后端返回错误',
          verifiedBy: '需检查',
          durationMs: 0,
        })
      }
    }
  } catch {
    // 用户取消对话框 — 不视为错误
  } finally {
    actionLoading.value = false
  }
}

/** Phase 3.8.4: 切换数据源启用/禁用 (更新 config.disabled 字段) */
async function onToggleSource(sourceId: string, willDisable: boolean) {
  const startTime = Date.now()
  const source = pipeline.dataSources.find(s => s.id === sourceId)
  if (!source) return
  try {
    const newCfg = { ...(source.config || {}), disabled: willDisable }
    // PLAN-006 / NEW-09 红线修复: 真实调用 PUT /datasources/{id} 持久化到后端。
    // 此前仅改前端 state 却在验证日志记 "PATCH ... success"，属伪造操作记录。
    const updated = await datasourceStore.updateSource(sourceId, { config: newCfg })
    if (!updated) {
      throw new Error(datasourceStore.error || '数据源状态持久化失败')
    }
    // 同步本地缓存与后端返回值，保证前后端一致
    const idx = pipeline.dataSources.findIndex(s => s.id === sourceId)
    if (idx >= 0) {
      pipeline.dataSources[idx] = { ...source, config: updated.config ?? newCfg }
    }
    const persistedDisabled = updated.config?.disabled ?? willDisable
    await verifyState(
      `${willDisable ? '禁用' : '启用'}数据源 ${getSourceNameLabel(source.name)}`,
      `PUT /datasources/${sourceId.slice(0, 8)}`,
      'success',
      `${getSourceNameLabel(source.name)} ${willDisable ? '已禁用' : '已启用'}（后端已持久化）`,
      Date.now() - startTime,
      async () => {
        // 验证: 以后端返回值为真相
        return {
          verified: persistedDisabled === willDisable,
          verifiedBy: `后端返回 ${getSourceNameLabel(source.name)}.config.disabled = ${persistedDisabled} (期望 ${willDisable})`,
          verifiedValue: { source: getSourceNameLabel(source.name), disabled: persistedDisabled },
        }
      },
    )
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '操作失败'
    ElMessage.error(`${msg}`)
  }
}

/** Phase 3.8.5: 强制推进卡死的 run (重新调用 advance_pipeline) */
async function onForceAdvance() {
  const runId = pipeline.pipelineStatus?.current_run?.id
  if (!runId) {
    ElMessage.warning('没有正在运行的流水线')
    return
  }
  try {
    await ElMessageBox.confirm(
      '强制推进会重新调用 advance_pipeline, 触发所有待执行阶段。可能用于修复 Celery event loop 错误导致的卡死。',
      '强制推进',
      { confirmButtonText: '确认推进', cancelButtonText: '取消', type: 'warning' }
    )
    actionLoading.value = true
    const startTime = Date.now()
    const ok = await pipeline.forceAdvance(runId)
    const duration = Date.now() - startTime
    if (ok) {
      await verifyState(
        '强制推进',
        `POST /pipeline/runs/${runId.slice(0, 8)}/force-advance`,
        'success',
        `Advanced in ${duration}ms`,
        duration,
        async () => {
          await pipeline.fetchStatus()
          await pipeline.fetchStages()
          // 验证: 现在应该没有 pending 阶段 (或正在 running)
          const stages = pipeline.stages.filter(s => s.status !== 'skipped')
          const stillPending = stages.filter(s => s.status === 'pending')
          const nowRunning = stages.filter(s => s.status === 'running')
          const verified = stillPending.length === 0 || nowRunning.length > 0
          return {
            verified,
            verifiedBy: `待执行=${stillPending.length}, 运行中=${nowRunning.length}`,
            verifiedValue: { pending: stillPending.length, running: nowRunning.length },
          }
        },
      )
    } else {
      ElMessage.error('强制推进失败, 请查看浏览器控制台')
    }
  } catch { /* 用户取消 */ } finally {
    actionLoading.value = false
  }
}

/** Phase 3.8.5: 强制重置卡死的 run (cancel + 标记所有 running/pending stage 为 cancelled) */
async function onForceReset() {
  const runId = pipeline.pipelineStatus?.current_run?.id
  if (!runId) {
    ElMessage.warning('没有正在运行的流水线')
    return
  }
  try {
    await ElMessageBox.confirm(
      '强制重置会把当前卡死的 run 标记为 cancelled, 并把所有 running/pending 阶段也标记为 cancelled。此操作不可撤销。',
      '强制重置',
      { confirmButtonText: '确认重置', cancelButtonText: '取消', type: 'warning' }
    )
    actionLoading.value = true
    const startTime = Date.now()
    const ok = await pipeline.forceReset(runId)
    const duration = Date.now() - startTime
    if (ok) {
      await verifyState(
        '强制重置',
        `POST /pipeline/runs/${runId.slice(0, 8)}/force-reset`,
        'success',
        `Reset in ${duration}ms`,
        duration,
        async () => {
          await pipeline.fetchStatus()
          await pipeline.fetchStages()
          const verified = !pipeline.pipelineStatus?.is_running
          return {
            verified,
            verifiedBy: `is_running = ${pipeline.pipelineStatus?.is_running} (期望 false)`,
            verifiedValue: { is_running: pipeline.pipelineStatus?.is_running },
          }
        },
      )
    } else {
      ElMessage.error('强制重置失败, 请查看浏览器控制台')
    }
  } catch { /* 用户取消 */ } finally {
    actionLoading.value = false
  }
}

/** 手动触发验证 - 重新检查当前所有状态 (Phase 3.8.1: 强制重新拉取避免 stale) */
async function verifyNow() {
  isVerifying.value = true
  try {
    // 强制并行重新拉取所有数据
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
    const summary = `KPI=${ps?.success_rate ? (ps.success_rate*100).toFixed(1) + '%' : '--'} | 数据源=${ps?.active_data_sources ?? '--'} | 阶段: ${running}运行/${completed}完成/${failed}失败/${cancelled}取消`
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
</script>

<template>
  <MainLayout>
    <div class="pipeline-page animate-fade-in">
      <BusinessBanner
        type="success"
        title="L2 数据融合层 — ETL 流水线监控"
        description="全链路 ETL DAG：爬虫采集 → 去重 → 清洗 → LLM 抽取 → 入库 → 图谱构建（Phase 3 串行化）。每个阶段独立降级，失败不阻塞后续流程。数据源质量影响 §7.1 信任度评分。"
        meta="后端: <code>/pipeline/*</code> · 数据源: <code>pipeline_runs</code> + Neo4j · SSE 实时推送"
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
        <!-- Phase 3 Plan 02: SSE 断开时用户可见提示 -->
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
            <!-- Phase 3.8 取消按钮 - 只在真正 running 时显示，terminal 状态隐藏 -->
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

      <!-- Phase 3.8.2: 状态摘要 Hero 卡片 (Phase 2 P3-1: 抽出 PipelineStatusHero) -->
      <PipelineStatusHero
        :is-running="pipeline.pipelineStatus?.is_running ?? false"
        :summary="stageSummary"
      />

      <!-- 4 个 KPI 卡片 (Phase 2 P3-1: 抽出 PipelineKpiCards) -->
      <PipelineKpiCards :cards="kpiCards" />

      <!-- Phase 16 数据审核闭环: 待审核提示 -->
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

      <!-- Phase 3.8.5: 卡死检测横幅 + 强制操作 -->
      <el-alert
        v-if="isStuck"
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
            <strong>症状:</strong> {{ stuckReason }}
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
              :loading="actionLoading"
              @click="onForceAdvance"
            >
              <el-icon style="vertical-align: middle">
                <Refresh />
              </el-icon>
              强制推进
            </el-button>
            <el-button
              type="danger"
              :loading="actionLoading"
              @click="onForceReset"
            >
              <el-icon style="vertical-align: middle">
                <Close />
              </el-icon>
              强制重置
            </el-button>
          </div>
        </div>
      </el-alert>

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

      <!-- Phase 3.8: 闭环验证日志面板 (替换单独实时面板) -->
      <el-card
        shadow="never"
        class="verify-log-card mb-4"
      >
        <template #header>
          <div class="panel-header">
            <span>
              <el-icon style="vertical-align: middle"><Check /></el-icon>
              闭环验证 (按钮 → API → 状态变化 → 验证)
              <!-- Phase 3.8.2: 持久化指示器 -->
              <el-tag
                v-if="actionLogs.length > 0"
                type="info"
                size="small"
                effect="plain"
                class="ml-2"
              >
                <el-icon :size="11"><Lock /></el-icon>
                {{ actionLogs.length }} 条历史
              </el-tag>
            </span>
            <div class="header-actions">
              <el-button
                v-if="actionLogs.length > 0"
                size="small"
                text
                @click="clearLogs"
              >
                清空
              </el-button>
              <el-tag
                v-if="isVerifying"
                type="info"
                size="small"
                effect="plain"
              >
                <el-icon
                  class="rotating"
                  :size="11"
                >
                  <Loading />
                </el-icon>
                验证中
              </el-tag>
              <el-tag
                v-else
                type="success"
                size="small"
                effect="plain"
              >
                <el-icon :size="11">
                  <Check />
                </el-icon>
                实时
              </el-tag>
            </div>
          </div>
        </template>
        <div
          v-if="actionLogs.length === 0"
          class="verify-empty"
        >
          <el-icon :size="32">
            <Connection />
          </el-icon>
          <p>尚无操作记录。点击上方任意按钮 (触发/取消/重试/校验) 即可在此查看完整闭环链路。</p>
        </div>
        <div
          v-else
          class="verify-log-list"
        >
          <div
            v-for="log in actionLogs"
            :key="log.id"
            class="verify-log-item"
            :class="`result-${log.result}`"
          >
            <div class="log-time">
              {{ logTime(log.timestamp) }}
              <span
                v-if="log.durationMs > 0"
                class="log-duration"
              >· {{ log.durationMs }}ms</span>
            </div>
            <div class="log-icon">
              <el-icon
                v-if="log.result === 'success'"
                :size="18"
                color="#16a34a"
              >
                <Check />
              </el-icon>
              <el-icon
                v-else-if="log.result === 'failed'"
                :size="18"
                color="#dc2626"
              >
                <Close />
              </el-icon>
              <el-icon
                v-else
                :size="18"
                color="#3b82f6"
                class="rotating"
              >
                <Loading />
              </el-icon>
            </div>
            <div class="log-content">
              <div class="log-action">
                {{ log.action }}
              </div>
              <div class="log-meta">
                <span class="log-endpoint"><code>{{ log.apiEndpoint }}</code></span>
                <span class="log-result-msg">{{ log.resultMessage }}</span>
              </div>
              <div class="log-verification">
                <el-icon
                  :size="11"
                  :color="log.result === 'failed' ? '#dc2626' : '#16a34a'"
                >
                  <Check />
                </el-icon>
                <span class="log-verify-text">{{ log.verifiedBy }}</span>
                <span
                  v-if="log.verifiedValue"
                  class="log-verify-value"
                >→ {{ JSON.stringify(log.verifiedValue) }}</span>
              </div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 底部：数据源面板 + 数据质量监控 -->
      <el-row :gutter="16">
        <!-- 左：数据源管理面板 (Phase 3.8.4 增强版) -->
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

        <!-- 右：数据质量实时监控 -->
        <el-col
          :lg="10"
          :md="24"
          class="mb-4"
        >
          <PipelineQualityPanel
            :data-quality="pipeline.dataQuality"
            :quality-trend-option="qualityTrendOption"
            :quality-trend-dir="qualityTrendDir"
            :loading="pipeline.loading"
          />
        </el-col>
      </el-row>

      <!-- 定时调度列表 -->
      <el-card
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
              @click="openScheduleDialog"
            >
              新增调度
            </el-button>
          </div>
        </template>
        <div
          v-if="!pipeline.schedules.length"
          class="schedule-empty"
        >
          <p>暂无定时调度。点击右上角"新增调度"创建第一个 Cron 计划。</p>
        </div>
        <el-table
          v-else
          :data="pipeline.schedules"
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
                {{ row.run_type === 'full' ? '全量' : '增量' }}
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
                @change="handleToggleSchedule(row)"
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
              {{ row.next_run_at ? new Date(row.next_run_at).toLocaleString() : '--' }}
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
                @click="handleTriggerSchedule(row)"
              >
                立即执行
              </el-button>
              <el-button
                size="small"
                type="danger"
                link
                @click="handleDeleteSchedule(row.id)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- ── 触发流水线弹窗 ── -->
      <el-dialog
        v-model="triggerDialogVisible"
        title="触发流水线"
        width="480px"
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
            <el-radio-group v-model="triggerRunType">
              <el-radio value="full">
                全量
              </el-radio>
              <el-radio value="incremental">
                增量
              </el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="执行阶段">
            <el-tooltip
              content="可选择部分阶段重跑（如仅重跑 import），未选阶段将标记为 skipped"
              placement="top"
              effect="dark"
            >
              <el-checkbox-group v-model="selectedStages">
                <el-checkbox
                  v-for="name in ALL_STAGE_NAMES"
                  :key="name"
                  :value="name"
                >
                  {{ STAGE_LABELS[name] || name }}
                </el-checkbox>
              </el-checkbox-group>
            </el-tooltip>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="triggerDialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            :disabled="selectedStages.length === 0"
            :loading="actionLoading"
            @click="handleTriggerWithVerify"
          >
            启动
          </el-button>
        </template>
      </el-dialog>

      <!-- ── 定时调度弹窗 ── -->
      <el-dialog
        v-model="scheduleDialogVisible"
        title="创建定时调度"
        width="480px"
        align-center
      >
        <el-form
          :model="scheduleForm"
          label-width="100px"
        >
          <el-form-item label="名称">
            <el-input
              v-model="scheduleForm.name"
              placeholder="如：每日增量爬取"
            />
          </el-form-item>
          <el-form-item label="Cron 表达式">
            <el-tooltip
              placement="top"
              effect="dark"
            >
              <template #content>
                <div style="line-height: 1.6">
                  格式: 分 时 日 月 周<br>
                  示例:<br>
                  <code>0 2 * * *</code> = 每天凌晨 2 点<br>
                  <code>*/15 * * * *</code> = 每 15 分钟<br>
                  <code>0 9 * * 1</code> = 每周一 9 点<br>
                  <code>0 0 1 * *</code> = 每月 1 号 0 点<br>
                  <code>30 8 * * 1-5</code> = 工作日 8:30
                </div>
              </template>
              <el-input
                v-model="scheduleForm.cron_expression"
                placeholder="分 时 日 月 周，如 0 2 * * *"
              />
            </el-tooltip>
            <div
              v-if="scheduleForm.cron_expression && scheduleForm.cron_expression.trim().split(/\s+/).length !== 5"
              class="cron-hint-error"
            >
              Cron 表达式需要 5 个字段（分 时 日 月 周）
            </div>
          </el-form-item>
          <el-form-item label="运行类型">
            <el-radio-group v-model="scheduleForm.run_type">
              <el-radio value="full">
                全量
              </el-radio>
              <el-radio value="incremental">
                增量
              </el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="scheduleForm.enabled" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="scheduleDialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            @click="handleCreateSchedule"
          >
            创建
          </el-button>
        </template>
      </el-dialog>

      <!-- ── 配置弹窗 ── -->
      <el-dialog
        v-model="configDialogVisible"
        title="流水线配置"
        width="480px"
      >
        <el-form
          v-if="pipeline.config"
          label-width="120px"
        >
          <el-form-item label="阶段超时(秒)">
            <el-input-number
              v-model="pipeline.config.stage_timeout"
              :min="60"
              :max="7200"
              :step="60"
            />
          </el-form-item>
          <el-form-item label="Worker并发数">
            <el-input-number
              v-model="pipeline.config.worker_concurrency"
              :min="1"
              :max="16"
            />
          </el-form-item>
          <el-form-item label="爬取并发数">
            <el-input-number
              v-model="pipeline.config.crawl_concurrency"
              :min="1"
              :max="20"
            />
          </el-form-item>
          <el-form-item label="最大重试次数">
            <el-input-number
              v-model="pipeline.config.retry_max"
              :min="0"
              :max="10"
            />
          </el-form-item>
          <el-form-item label="重试间隔(秒)">
            <el-input-number
              v-model="pipeline.config.retry_backoff"
              :min="5"
              :max="300"
              :step="5"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="configDialogVisible = false">
            取消
          </el-button>
          <el-button
            v-if="pipeline.config"
            type="primary"
            :loading="configSaving"
            @click="handleSaveConfig"
          >
            保存
          </el-button>
        </template>
      </el-dialog>
    </div>

    <!-- Phase 3.8.5: 术语词典 (新手指引) -->
    <PipelineGlossary v-model="glossaryVisible" />
  </MainLayout>
</template>

<style scoped>
.pipeline-page {
  max-width: 1200px;
  margin: 0 auto;
}

/* Phase 26: 业务说明横幅 — 已迁移到 BusinessBanner.vue */


/* 页面头部 */
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

/* KPI 卡片 */
.kpi-card {
  cursor: default;
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}
.kpi-card::before {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 4%, transparent), transparent);
  transition: opacity var(--duration-normal);
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.kpi-card:hover::before { opacity: 1; }
.kpi-inner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  position: relative;
  z-index: 1;
}
.kpi-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.kpi-body {
  flex: 1;
  min-width: 0;
}
.kpi-label {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  font-weight: 500;
}
.kpi-value {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: var(--tracking-tight);
  font-variant-numeric: tabular-nums;
}
.kpi-sub {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  margin-top: var(--space-1);
}
.trend-up {
  color: var(--success);
  font-weight: 600;
}
.trend-down {
  color: var(--destructive);
  font-weight: 600;
}

/* 面板头部 */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mb-4 { margin-bottom: var(--space-4); }
.ml-2 { margin-left: var(--space-2); }

/* Phase 3.8.4: 面板标题 + 帮助图标 */
.panel-title {
  font-weight: 600;
  margin-right: 6px;
}
.help-icon {
  color: var(--muted-foreground);
  font-size: 13px;
  cursor: help;
}

/* Phase 3.8.5: 卡死横幅 */
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
.help-icon:hover { color: var(--primary); }

.schedule-empty {
  text-align: center;
  padding: var(--space-6) var(--space-4);
  color: var(--muted-foreground);
  font-size: 13px;
  background: var(--muted);
  border-radius: 6px;
}

@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .header-actions { width: 100%; justify-content: flex-start; }
  .kpi-value { font-size: var(--font-size-2xl); }
}

/* Phase 3.8 闭环验证面板 */
/* Phase 3.8.2 状态 Hero 卡片 */
.status-hero-card {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 50%, #ddd6fe 100%);
  border: 1px solid #93c5fd;
  border-left: 4px solid #3b82f6;
}
.status-hero-card :deep(.el-card__body) {
  padding: var(--space-4) var(--space-5);
}
.hero-content {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.hero-icon {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.hero-text { flex: 1; min-width: 0; }
.hero-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--foreground);
  margin-bottom: 4px;
}
.hero-detail {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
}
.hero-pill {
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 11px;
}
.hero-pill.completed { background: #dcfce7; color: #166534; }
.hero-pill.running { background: #dbeafe; color: #1d4ed8; }
.hero-pill.failed { background: #fee2e2; color: #991b1b; }
.hero-pill.cancelled { background: #fef3c7; color: #92400e; }
.hero-pill.skipped { background: #f1f5f9; color: #475569; }
.hero-meta {
  color: var(--muted-foreground);
  margin-left: var(--space-2);
}
.hero-meta strong { color: var(--foreground); font-weight: 700; }

.verify-log-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-bottom: 2px solid #0ea5e9;
}
.verify-empty {
  text-align: center;
  padding: var(--space-6);
  color: var(--muted-foreground);
}
.verify-empty p {
  margin: var(--space-2) 0 0 0;
  font-size: var(--font-size-sm);
}
.cron-hint-error {
  color: var(--el-color-danger);
  font-size: var(--font-size-xs);
  margin-top: 4px;
}
.verify-log-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 360px;
  overflow-y: auto;
}
.verify-log-item {
  display: grid;
  grid-template-columns: 80px 28px 1fr;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
  font-size: var(--font-size-sm);
  background: var(--card);
  transition: background 0.2s;
}
.verify-log-item:hover {
  background: var(--muted);
}
.verify-log-item:last-child {
  border-bottom: none;
}
.verify-log-item.result-failed {
  background: linear-gradient(90deg, #fef2f2 0%, transparent 30%);
  border-left: 3px solid #dc2626;
}
.verify-log-item.result-success {
  border-left: 3px solid #16a34a;
}
.verify-log-item.result-pending {
  border-left: 3px solid #3b82f6;
  background: linear-gradient(90deg, #eff6ff 0%, transparent 30%);
}
.log-time {
  font-size: 11px;
  color: var(--muted-foreground);
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', monospace);
  white-space: nowrap;
}
.log-duration {
  color: #6b7280;
  font-size: 10px;
  margin-left: 4px;
}
.log-icon {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 2px;
}
.log-content {
  min-width: 0;
}
.log-action {
  font-weight: 600;
  color: var(--foreground);
  margin-bottom: 2px;
}
.log-meta {
  display: flex;
  gap: var(--space-3);
  font-size: 11px;
  color: var(--muted-foreground);
  margin-bottom: 2px;
  flex-wrap: wrap;
}
.log-endpoint code {
  background: var(--muted);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', monospace);
  font-size: 10px;
}
.log-result-msg {
  color: var(--foreground);
  font-size: 11px;
}
.log-verification {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--foreground);
  flex-wrap: wrap;
  padding: 4px 6px;
  background: rgba(34, 197, 94, 0.08);
  border-radius: 4px;
  margin-top: 4px;
}
.log-verify-text {
  color: var(--foreground);
  font-weight: 500;
}
.log-verify-value {
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', monospace);
  font-size: 10px;
  color: var(--muted-foreground);
  word-break: break-all;
}
.rotating {
  animation: rotate 1s linear infinite;
}
@keyframes rotate {
  to { transform: rotate(360deg); }
}
</style>
