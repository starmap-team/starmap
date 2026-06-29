import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

export interface ParsedSkill {
  skill: string
  category: 'hard_skill' | 'soft_skill'
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
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000, // LLM 抽取需要更长时间，120秒超时
      })
      result.value = data as unknown as ResumeParseResult
    } finally {
      loading.value = false
    }
  }

  return { result, loading, parseResume }
})
