import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

export interface ParsedSkill {
  skill: string
  category: 'hard_skill' | 'soft_skill' | 'tool'
  proficiency: '了解' | '熟悉' | '精通'
}

export interface ResumeParseResult {
  position_name: string
  required_skills: ParsedSkill[]
  preferred_skills: ParsedSkill[]
  experience_required: number
  education_required: string
  confidence: number
  hallucination_score: number | null
  normalized_skills: { original: string; normalized: string; method: string; confidence: number }[]
}

export const useResumeStore = defineStore('resume', () => {
  const result = ref<ResumeParseResult | null>(null)
  const loading = ref(false)

  async function parseResume(file: File) {
    loading.value = true
    const formData = new FormData()
    formData.append('file', file)
    try {
      const data = await request.post('/resume/upload', formData, {
        timeout: 60000, // 60秒超时（LLM 抽取需要时间）
      })
      result.value = data as unknown as ResumeParseResult
    } catch (e: any) {
      console.error('[Resume] Parse failed:', e)
      result.value = null
      throw e // 向上传播错误，让调用方处理
    } finally {
      loading.value = false
    }
  }

  return { result, loading, parseResume }
})
