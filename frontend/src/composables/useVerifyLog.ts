/**
 * 闭环验证日志 composable（ Plan 03 从 PipelineMonitor.vue 抽出）。
 *
 * 每个操作记录: action, result, verification, timestamp；持久化到 localStorage。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

export interface ActionLog {
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

// FIX: 闭环验证日志持久化到 localStorage (解决刷新后数据丢失)
const VERIFY_LOG_KEY = 'starmap_pipeline_verify_log_v1'
const VERIFY_LOG_MAX = 30

export function useVerifyLog() {
  const actionLogs = ref<ActionLog[]>([])
  const isVerifying = ref(false)

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
 //: defensive against invalid timestamps (NaN, undefined, negative)
    if (typeof ts !== 'number' || !Number.isFinite(ts) || ts < 0) return '--:--:--'
    return new Date(ts).toLocaleTimeString('zh-CN', { hour12: false })
  }

 /** 核心: 每次操作后自动验证 */
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
 // FIX: 先 sleep 800ms 等待 store 实际更新 (避免 race condition)
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

  return {
    actionLogs,
    isVerifying,
    appendLog,
    clearLogs,
    logTime,
    verifyState,
  }
}
