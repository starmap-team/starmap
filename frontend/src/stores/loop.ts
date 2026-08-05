/**
 * 闭环演示 Pinia Store
 * 管理闭环运行状态、步骤结果、历史记录
 *
 * Phase 6 D-13 disposition: this store stays as its own file rather than being
 * mechanically merged into `pipeline.ts`. The two stores cover different state domains
 * (DAG scheduling vs 闭环 5-step pipeline) and the only overlap is the underlying
 * axios `request` import. A mechanical merge would couple unrelated domains and force
 * store-level refactor of every consumer (`pages/LoopDemo.vue`, `pages/PipelineMonitor.vue`).
 * When pipeline orchestration and closed-loop orchestration actually share state
 * (Phase 7+), revisit — until then this is the cheaper cut.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/api/request'
import type { GapLevel } from '@/stores/match'
import { useResponseValidation } from '@/validation/useResponseValidation'
import loopSchema from '@contracts/schemas/loop.schema.json'

// PLAN-014: 契约响应校验 (DEV warn 不阻断)
const { validateResponse: validateLoop } = useResponseValidation()

/** Timeout for the loop run API call (LLM extraction can take ~3 minutes) */
const LOOP_RUN_TIMEOUT_MS = 180_000

// ── 类型定义 ──

export type StepStatus = 'waiting' | 'running' | 'success' | 'degraded' | 'failed'

export interface StepResult {
  step: number
  name: string
  status: StepStatus
  duration_ms?: number
  // ponytail: data shape varies by step; Record<string,unknown> breaks template
  // arithmetic/method calls in LoopDemo.vue. Discriminated union won't work
  // because consumers access via steps[N].data without narrowing. Revisit when
  // LoopDemo.vue adds step-indexed type guards.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data?: any
  error?: string
  warning?: string
}

export interface ExtractedSkill {
  skill: string
  confidence: number
  is_new: boolean
  hallucination_score?: number
}

export interface GraphUpdateNode {
  id: string
  name: string
  type: string
  is_new: boolean
  x?: number
  y?: number
}

export interface GraphUpdateEdge {
  source: string
  target: string
  type: string
  is_new: boolean
}

export interface MatchDiagnosisResult {
  match_score: number
  matched_skills: string[]
  missing_skills: string[]
  gap_analysis: { skill: string; gap_level: GapLevel; importance: string }[]
  radar_data?: { skill: string; required: number; matched: number }[]
}

export interface LoopPathItem {
  skill: string
  sequence: number
  estimated_hours: number
  prerequisites: string[]
}

export interface LoopRun {
  run_id: string
  status: 'running' | 'completed' | 'partial'
  jd_text?: string
  target_position?: string
  steps: StepResult[]
  total_duration_ms?: number
  created_at?: string
}

// /loop/history returns full LoopResult dicts (from LoopResult.to_dict()),
// not a slim summary. We keep just the fields the table template needs;
// everything else is present on the item and ignored by el-table.
export interface LoopHistoryItem {
  run_id: string
  target_position?: string | null
  status: string
  steps?: { step: number; name: string; status: string; duration_seconds?: number; data?: Record<string, unknown>; error?: string | null; note?: string | null }[]
  total_duration_seconds?: number
  created_at?: string
}

// ── Store ──

export const useLoopStore = defineStore('loop', () => {
  const currentRun = ref<LoopRun | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const history = ref<LoopHistoryItem[]>([])

  // ── 计算属性 ──

  const currentStepIndex = computed(() => {
    if (!currentRun.value) return -1
    const running = currentRun.value.steps.findIndex(s => s.status === 'running')
    if (running >= 0) return running
    // 找最后一个完成的步骤
    for (let i = currentRun.value.steps.length - 1; i >= 0; i--) {
      if (currentRun.value.steps[i].status !== 'waiting') return i
    }
    return -1
  })

  const completedSteps = computed(() => {
    if (!currentRun.value) return 0
    return currentRun.value.steps.filter(s => s.status === 'success' || s.status === 'degraded').length
  })

  const isRunning = computed(() => loading.value || (currentRun.value?.status === 'running'))

  const totalDuration = computed(() => {
    if (!currentRun.value) return 0
    return currentRun.value.steps.reduce((sum, s) => sum + (s.duration_ms ?? 0), 0)
  })

  // ── 步骤名称 ──

  const STEP_NAMES = ['JD 输入', '技能提取', '图谱更新', '匹配诊断', '学习路径']

  function initSteps(): StepResult[] {
    return STEP_NAMES.map((name, i) => ({
      step: i + 1,
      name,
      status: 'waiting' as StepStatus,
    }))
  }

  // ── Actions ──

  /** 触发端到端闭环 */
  async function runLoop(jdText: string, targetPosition?: string) {
    loading.value = true
    error.value = null
    currentRun.value = {
      run_id: `run_${Date.now()}`,
      status: 'running',
      jd_text: jdText,
      target_position: targetPosition,
      steps: initSteps(),
      created_at: new Date().toISOString(),
    }

    try {
      // Step 1: JD 输入 (immediate success)
      currentRun.value.steps[0].status = 'success'
      currentRun.value.steps[0].duration_ms = 50

      // Step 2-5: 调用后端闭环 API
      const startTime = Date.now()
      const data = await request.post('/loop/run', {
        jd_text: jdText,
        target_position: targetPosition,
      }, { timeout: LOOP_RUN_TIMEOUT_MS }) as LoopRunResponse

      const totalTime = Date.now() - startTime

      // 解析后端返回的步骤结果
      if (data.steps && Array.isArray(data.steps)) {
        for (const stepData of data.steps) {
          const idx = stepData.step - 1
          if (idx >= 0 && idx < currentRun.value.steps.length) {
            currentRun.value.steps[idx].status = stepData.status ?? 'success'
            // Backend returns `duration_seconds`; convert to ms for the UI.
            // (Backwards-compat: fall back to `duration_ms` if some other
            // payload still uses the old field name.)
            const durSec = (stepData as { duration_seconds?: number }).duration_seconds
            const durMs = (stepData as { duration_ms?: number }).duration_ms
            currentRun.value.steps[idx].duration_ms =
              durMs ?? (durSec != null ? Math.round(durSec * 1000) : undefined)
            currentRun.value.steps[idx].data = stepData.data
            currentRun.value.steps[idx].error = stepData.error
            currentRun.value.steps[idx].warning = stepData.warning
          }
        }
      } else {
        // 兼容：如果没有 steps 数组，把整体结果放到各步骤
        parseFlatResult(data, totalTime)
      }

      currentRun.value.status = data.status ?? 'completed'
      currentRun.value.total_duration_ms = totalTime
      currentRun.value.run_id = data.run_id ?? currentRun.value.run_id
    } catch (e: unknown) {
      // fix: HTTPException.detail 在 axios 错误对象里位于 response.data.detail，message 字段是 axios 默认文案
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      error.value = detail ?? (e instanceof Error ? e.message : '闭环执行失败')
      // 标记当前运行的步骤为失败
      if (currentRun.value) {
        const runningStep = currentRun.value.steps.find(s => s.status === 'running')
        if (runningStep) {
          runningStep.status = 'failed'
          runningStep.error = error.value ?? undefined
        }
        currentRun.value.status = 'partial'
      }
    } finally {
      loading.value = false
    }
  }

  /** 兼容解析：后端返回扁平结果时分配到各步骤 */
  // ponytail: response shape from /loop/run; expand if contract changes
  interface LoopRunResponse {
    steps?: { step: number; status?: StepStatus; duration_ms?: number; duration_seconds?: number; data?: Record<string, unknown>; error?: string; warning?: string }[]
    status?: 'running' | 'completed' | 'partial'
    run_id?: string
    extracted_skills?: unknown[]
    required_skills?: unknown[]
    confidence?: number
    hallucination_score?: number
    graph_update?: Record<string, unknown>
    new_nodes?: unknown[]
    existing_nodes?: unknown[]
    new_edges?: unknown[]
    graph_degraded?: boolean
    match_result?: Record<string, unknown>
    match_score?: number
    matched_skills?: string[]
    missing_skills?: string[]
    gap_analysis?: unknown[]
    radar_data?: unknown[]
    match_degraded?: boolean
    learning_path?: unknown[]
    learning_paths?: unknown[]
    estimated_learning_hours?: number
    learning_degraded?: boolean
  }

  // ponytail: single interface for the flat backend response shape; expand if contract changes
  interface FlatLoopResult {
    extracted_skills?: unknown[]
    required_skills?: unknown[]
    confidence?: number
    hallucination_score?: number
    graph_update?: Record<string, unknown>
    new_nodes?: unknown[]
    existing_nodes?: unknown[]
    new_edges?: unknown[]
    graph_degraded?: boolean
    match_result?: Record<string, unknown>
    match_score?: number
    matched_skills?: string[]
    missing_skills?: string[]
    gap_analysis?: unknown[]
    radar_data?: unknown[]
    match_degraded?: boolean
    learning_path?: unknown[]
    learning_paths?: unknown[]
    estimated_learning_hours?: number
    learning_degraded?: boolean
  }

  function parseFlatResult(data: FlatLoopResult, totalTime: number) {
    if (!currentRun.value) return
    const steps = currentRun.value.steps

    // Step 2: 技能提取
    if (data.extracted_skills || data.required_skills) {
      steps[1].status = 'success'
      steps[1].duration_ms = Math.round(totalTime * 0.25)
      steps[1].data = {
        skills: data.extracted_skills ?? data.required_skills ?? [],
        // PLAN-006③ 红线: 后端无值时不再编造 0.85/0.1, 交 undefined 由展示层显"未评估"
        confidence: data.confidence ?? undefined,
        hallucination_score: data.hallucination_score ?? undefined,
      }
    }

    // Step 3: 图谱更新
    if (data.graph_update || data.new_nodes) {
      steps[2].status = data.graph_degraded ? 'degraded' : 'success'
      steps[2].duration_ms = Math.round(totalTime * 0.2)
      steps[2].data = data.graph_update ?? {
        new_nodes: data.new_nodes ?? [],
        existing_nodes: data.existing_nodes ?? [],
        new_edges: data.new_edges ?? [],
      }
      if (data.graph_degraded) {
        steps[2].warning = '基于历史图谱，新增节点未纳入'
      }
    }

    // Step 4: 匹配诊断
    if (data.match_result || data.match_score !== undefined) {
      steps[3].status = data.match_degraded ? 'degraded' : 'success'
      steps[3].duration_ms = Math.round(totalTime * 0.3)
      steps[3].data = data.match_result ?? {
        match_score: data.match_score ?? 0,
        matched_skills: data.matched_skills ?? [],
        missing_skills: data.missing_skills ?? [],
        gap_analysis: data.gap_analysis ?? [],
        radar_data: data.radar_data ?? [],
      }
    }

    // Step 5: 学习路径
    if (data.learning_path || data.learning_paths) {
      steps[4].status = data.learning_degraded ? 'degraded' : 'success'
      steps[4].duration_ms = Math.round(totalTime * 0.2)
      steps[4].data = {
        paths: data.learning_path ?? data.learning_paths ?? [],
        estimated_total_hours: data.estimated_learning_hours ?? 0,
      }
    }
  }

  /** 获取运行状态 */
  async function getStatus(runId: string) {
    try {
      const data = validateLoop(
        await request.get(`/loop/status/${runId}`) as Record<string, unknown>,
        loopSchema, `/loop/status/${runId}`, 'LoopRunResponse',
      ) as Record<string, unknown>
      return data
    } catch {
      return null
    }
  }

  /** 获取历史记录 */
  async function fetchHistory() {
    try {
      const data = validateLoop(
        await request.get('/loop/history', { params: { limit: 20 } }) as { items?: LoopHistoryItem[] },
        loopSchema, '/loop/history', 'LoopHistoryResponse',
      ) as { items?: LoopHistoryItem[] }
      history.value = data.items ?? []
    } catch {
      history.value = []
    }
  }

  /** 重置当前运行 */
  function resetRun() {
    currentRun.value = null
    error.value = null
  }

  return {
    // State
    currentRun,
    loading,
    error,
    history,
    // Computed
    currentStepIndex,
    completedSteps,
    isRunning,
    totalDuration,
    // Constants
    STEP_NAMES,
    // Actions
    runLoop,
    getStatus,
    fetchHistory,
    resetRun,
  }
})
