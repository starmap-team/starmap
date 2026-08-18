/**
 * 触发/取消/重试/续跑/强制操作 composable（ Plan 03 Task 8 实际迁移）。
 *
 * 从 usePipelineMonitor.ts 抽出触发流水线相关状态与操作：
 * 触发对话框状态、actionLoading、重试中阶段、取消/重试/续跑/强制推进/强制重置。
 */
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePipelineRunStore } from '@/stores/pipelineRun'
import { ALL_STAGE_NAMES, STAGE_LABELS } from '@/stores/pipelineConfig'
import { RUN_TYPE_LABELS } from '@/constants/labels'

export type TriggerRunType = 'full' | 'incremental'

export interface TriggerPipelineOptions {
 /** 触发成功后回调（页面用于刷新 + 加速轮询） */
  onAfterTrigger?: () => Promise<void> | void
 /** 操作成功后刷新全页面（loadAll） */
  onAfterMutation?: () => Promise<void> | void
}

export function useTriggerPipeline(options: TriggerPipelineOptions = {}) {
  const runStore = usePipelineRunStore()
  const actionLoading = ref(false)
  const retryingStages = ref<Set<string>>(new Set())

 // ── 触发对话框状态 ──
  const selectedStages = ref<string[]>(ALL_STAGE_NAMES)
 // D8: 手动触发自选源（空数组 = 全部源）
  const selectedSources = ref<string[]>([])
  const triggerDialogVisible = ref(false)
  const triggerRunType = ref<TriggerRunType>('full')

  function openTriggerDialog() {
    selectedStages.value = ALL_STAGE_NAMES
    selectedSources.value = []  // 默认全部源
    triggerRunType.value = 'full'
    triggerDialogVisible.value = true
  }

 // ──-02 (Fix B2): 用 last_run.id fallback, 让 failed/cancelled run 也能重试 ──
  const currentRunId = computed(() => {
    return runStore.pipelineStatus?.last_run?.id
      ?? runStore.pipelineStatus?.current_run?.id
      ?? null
  })

  async function trigger(
    stages: string[],
    runType: TriggerRunType = 'full',
    sources?: string[],
  ) {
 // 2026-08-12 (pipeline 修复): 防重入 —— 触发请求进行中忽略重复点击。
 // 之前 run 在 ~1s 内跑完，连点"触发流水线/续跑"会瞬间产生 3~5 条新 run。
    if (actionLoading.value) {
      ElMessage.info('流水线正在触发中，请稍候…')
      return false
    }
    actionLoading.value = true
    try {
 //: 触发新 run 时清空实时活动缓存
      runStore.resetLiveActivity()
 // D8: sources 传入选源（空/未传 = 全部源）
      await runStore.triggerPipeline(runType, stages, sources?.length ? sources : undefined)
      const runTypeLabel = RUN_TYPE_LABELS[runType] ?? runType
      const sourceNote = sources?.length ? `，${sources.length} 个数据源` : ''
      ElMessage.success(`流水线已触发（${runTypeLabel}，${stages.length} 个阶段${sourceNote}）`)
      await options.onAfterTrigger?.()
      return true
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '触发失败，请检查后端服务状态'
      ElMessage.error(`触发失败：${msg}`)
      return false
    } finally {
      actionLoading.value = false
    }
  }

  async function handleRetryStage(stageName: string) {
    if (!currentRunId.value) {
      ElMessage.warning('没有可重试的运行')
      return
    }
    retryingStages.value.add(stageName)
    try {
      await runStore.retryStage(currentRunId.value, stageName)
 // 刷全页面：重试后 DAG 需要反映阶段状态变化
      await options.onAfterMutation?.()
      ElMessage.success(`阶段「${STAGE_LABELS[stageName] || stageName}」已重新调度执行`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '重试失败'
      ElMessage.error(`重试失败：${msg}`)
    } finally {
      retryingStages.value.delete(stageName)
    }
  }

  async function handleResume(runId?: string) {
 // 2026-08-12 (pipeline 修复): RunHistory 每行的"续跑"按钮会传 row.id，但此前
 // handleResume 不接收参数，固定用 recent_failed_run 兜底 —— 当另一 run 正在执行
 // (recent_failed_run=null) 时会把已完成/运行中的 run 误续跑。现在优先用传入的
 // runId（被点击行），无参（页面头部"断点续跑"按钮）才回退到 recent_failed_run。
    const failedRunId = runId ?? runStore.pipelineStatus?.recent_failed_run?.id ?? currentRunId.value
    if (!failedRunId) {
      ElMessage.warning('没有可续跑的运行')
      return
    }
    actionLoading.value = true
    try {
      await runStore.resumeRun(failedRunId)
 // 刷全页面：断点续跑后 status→running，按钮需切换，DAG 需更新
      await options.onAfterMutation?.()
      ElMessage.success('断点续跑已启动，将从失败阶段继续执行')
      await options.onAfterTrigger?.() // 执行期间加速刷新
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '续跑失败'
      ElMessage.error(`断点续跑失败：${msg}`)
    } finally {
      actionLoading.value = false
    }
  }

 /** 取消运行（带确认）。返回 true 表示取消成功。 */
  async function cancelRun(runId: string): Promise<boolean> {
    try {
      await ElMessageBox.confirm(
        '确认取消当前正在运行的流水线？此操作不可撤销。',
        '取消流水线',
        { confirmButtonText: '确认取消', cancelButtonText: '不取消', type: 'warning' }
      )
      actionLoading.value = true
      const ok = await runStore.cancelRun(runId)
      if (ok) {
        await options.onAfterMutation?.()
        ElMessage.success('流水线已取消，所有运行中阶段已停止')
      } else {
        ElMessage.error('取消失败，请查看控制台错误信息')
      }
      return ok
    } catch {
 // 用户取消对话框 — 不视为错误
      return false
    } finally {
      actionLoading.value = false
    }
  }

 /** 强制推进卡死 run（带确认）。 */
  async function forceAdvance(runId: string): Promise<boolean> {
    try {
      await ElMessageBox.confirm(
        '强制推进会重新调用 advance_pipeline, 触发所有待执行阶段。可能用于修复 Celery event loop 错误导致的卡死。',
        '强制推进',
        { confirmButtonText: '确认推进', cancelButtonText: '取消', type: 'warning' }
      )
      actionLoading.value = true
      return await runStore.forceAdvance(runId)
    } catch {
      return false
    } finally {
      actionLoading.value = false
    }
  }

 /** 强制重置卡死 run（带确认）。 */
  async function forceReset(runId: string): Promise<boolean> {
    try {
      await ElMessageBox.confirm(
        '强制重置会把当前卡死的 run 标记为 cancelled, 并把所有 running/pending 阶段也标记为 cancelled。此操作不可撤销。',
        '强制重置',
        { confirmButtonText: '确认重置', cancelButtonText: '取消', type: 'warning' }
      )
      actionLoading.value = true
      return await runStore.forceReset(runId)
    } catch {
      return false
    } finally {
      actionLoading.value = false
    }
  }

  return {
    actionLoading,
    retryingStages,
    currentRunId,
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
  }
}
