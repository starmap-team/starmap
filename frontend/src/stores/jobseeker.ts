/** 求职者业务闭环分析 Store。 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import type { GapLevel } from '@/stores/match'
import { API_BASE } from '@/config/apiBase'

export interface ExtractedSkill {
  name: string
  raw_name: string
  category: string
  proficiency: string
  confidence: number
}

export interface TopMatch {
  position: string
  match_score: number
  assessment: string
  gap_count: number
}

export interface RecommendedPosition {
  position: string
  score: number
  match_score: number
  developability: number
  market_demand: number
}

export interface LearningResource {
  name: string
  url: string
  type: string
}

export interface SkillGap {
  skill: string
  importance: string
  gap_level: GapLevel
  learning_path: string[]
  learning_resources: LearningResource[]
  score: number
}

export interface PipelineResult {
  extracted_skills: ExtractedSkill[]
  top_matches: TopMatch[]
  recommended_positions: RecommendedPosition[]
  skill_gaps: SkillGap[]
  learning_path_summary: string[][]
  data_source: string
  errors: string[]
}

export interface ProgressEvent {
  step: string
  status: string
  error?: string
}

/** 步骤验证检查项 */
export interface VerificationCheck {
  check: string
  ok: boolean
  detail: string
}

/** 步骤输出摘要（: 逐步可视化核验） */
export interface StepOutputSample {
  label?: string
  value?: unknown
 /** 后端多样样本结构（name/category/confidence / text_preview / position 等） */
  name?: string
  position?: string
  [key: string]: unknown
}

export interface StepOutput {
  step: string
  display_name: string
  status: string
  input_summary: Record<string, unknown>
  output_summary: Record<string, unknown>
  samples: StepOutputSample[]
  verification: {
    passed: boolean
    checks: VerificationCheck[]
  }
  error?: string
}

export const useJobseekerStore = defineStore('jobseeker', () => {
  const loading = ref(false)
  const progress = ref<ProgressEvent[]>([])
  const currentStep = ref('')
  const result = ref<PipelineResult | null>(null)
  const error = ref<string | null>(null)
 /**: 逐步可视化核验 — 每步的输出详情 */
  const stepOutputs = ref<StepOutput[]>([])

 /** 上传简历并执行 Pipeline 分析（SSE 模式）。 */
  async function analyzeResume(file: File, targetPositions?: string[]) {
    loading.value = true
    progress.value = []
    stepOutputs.value = []
    result.value = null
    error.value = null
 // P3 fix ( 求职者分析): AbortController 支持组件卸载/超时中止，
 // 避免请求悬挂时 loading 永远 true。超时 300s 对齐后端 LLM 降级链。
    const controller = new AbortController()
    const timeoutId = window.setTimeout(() => controller.abort(), 300_000)
    try {
      const formData = new FormData()
      formData.append('resume_file', file)
      if (targetPositions?.length) {
        formData.append('target_positions', targetPositions.join(','))
      }

 // LOOP-02: Add Authorization header + fix hardcoded URL
      const baseUrl = API_BASE
      const token = localStorage.getItem('starmap_access_token')
      const headers: Record<string, string> = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }
      const response = await fetch(`${baseUrl}/pipeline/analyze`, {
        method: 'POST',
        body: formData,
        headers,
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const body = response.body  // ponytail: null guard instead of !
      if (!body) throw new Error('ReadableStream not available')
      const reader = body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

 // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let currentEvent = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6)
            try {
              const data = JSON.parse(dataStr)
              if (currentEvent === 'progress') {
                progress.value.push(data)
                currentStep.value = data.step
              } else if (currentEvent === 'result') {
 // P2 fix (functional-review 2026-08-13): SSE result 事件直接赋给
 // result.value 无字段归一化 —— PipelineAnalysis.vue 模板访问
 // result.extracted_skills.length 等，后端若缺任一数组字段即抛
 // TypeError（页面异常）。统一补齐数组字段默认值。
                const rawResult = (data ?? {}) as Record<string, unknown>
 // P0 fix ( 求职者分析): learning_path_summary 元素可能为
 // None（后端 gap.learning_path 显式 null）——模板 v-for path.length
 // 崩溃。统一过滤非数组元素；skill_gaps 同兜底。
                const rawPaths = Array.isArray(rawResult.learning_path_summary)
                  ? rawResult.learning_path_summary
                  : []
                const rawGaps = Array.isArray(rawResult.skill_gaps) ? rawResult.skill_gaps : []
                result.value = {
                  ...rawResult,
                  extracted_skills: Array.isArray(rawResult.extracted_skills) ? rawResult.extracted_skills : [],
                  top_matches: Array.isArray(rawResult.top_matches) ? rawResult.top_matches : [],
                  recommended_positions: Array.isArray(rawResult.recommended_positions) ? rawResult.recommended_positions : [],
                  skill_gaps: rawGaps.map((g: Record<string, unknown>) => ({
                    ...g,
                    learning_path: Array.isArray(g.learning_path) ? g.learning_path : [],
                    learning_resources: Array.isArray(g.learning_resources) ? g.learning_resources : [],
                  })),
                  learning_path_summary: rawPaths.filter(p => Array.isArray(p)),
                  errors: Array.isArray(rawResult.errors) ? rawResult.errors : [],
                } as PipelineResult
              } else if (currentEvent === 'step_output') {
 //: 接收步骤输出详情供可视化核验
                stepOutputs.value.push(data as StepOutput)
              }
            } catch {
 // 忽略非 JSON 数据
            }
          }
        }
      }
    } catch (e: unknown) {
      window.clearTimeout(timeoutId)
      error.value = e instanceof Error
        ? (e.name === 'AbortError' ? '分析超时，请重试或更换网络' : e.message)
        : '分析失败'
    } finally {
      window.clearTimeout(timeoutId)
      loading.value = false
    }
  }

  function reset() {
    loading.value = false
    progress.value = []
    stepOutputs.value = []
    currentStep.value = ''
    result.value = null
    error.value = null
  }

  return {
    loading,
    progress,
    currentStep,
    result,
    error,
    stepOutputs,
    analyzeResume,
    reset,
  }
})
