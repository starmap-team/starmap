/** 求职者业务闭环分析 Store。 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

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
  gap_level: string
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

export const useJobseekerStore = defineStore('jobseeker', () => {
  const loading = ref(false)
  const progress = ref<ProgressEvent[]>([])
  const currentStep = ref('')
  const result = ref<PipelineResult | null>(null)
  const error = ref<string | null>(null)

  /** 上传简历并执行 Pipeline 分析（SSE 模式）。 */
  async function analyzeResume(file: File, targetPositions?: string[]) {
    loading.value = true
    progress.value = []
    result.value = null
    error.value = null

    try {
      const formData = new FormData()
      formData.append('resume_file', file)
      if (targetPositions?.length) {
        formData.append('target_positions', targetPositions.join(','))
      }

      const response = await fetch('/api/v1/pipeline/analyze', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body!.getReader()
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
                result.value = data
              }
            } catch {
              // 忽略非 JSON 数据
            }
          }
        }
      }
    } catch (e: any) {
      error.value = e.message || '分析失败'
    } finally {
      loading.value = false
    }
  }

  function reset() {
    loading.value = false
    progress.value = []
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
    analyzeResume,
    reset,
  }
})
