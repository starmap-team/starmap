/**
 * Prompt template management store — consumed by PromptManager.vue.
 * Wraps /admin/prompts/* endpoints for version management + A/B testing.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

export interface PromptVersionInfo {
  versions: string[]
  active: string | null
  ab_test: {
    prompt_name: string
    control_version: string
    canary_version: string
    traffic_fraction: number
  } | null
}

export interface ABResultSummary {
  count: number
  success_rate: number
  avg_f1: number | null
  avg_latency_ms: number | null
}

export const usePromptStore = defineStore('prompt', () => {
  const prompts = ref<Record<string, PromptVersionInfo>>({})
  const currentTemplate = ref('')
  const abResults = ref<Record<string, ABResultSummary>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchPrompts() {
    loading.value = true
    error.value = null
    try {
      const data = await request.get('/admin/prompts') as Record<string, PromptVersionInfo>
      prompts.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取Prompt列表失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchTemplate(name: string, version?: string) {
    try {
      const params = version ? `?version=${version}` : ''
      const data = await request.get(`/admin/prompts/${name}/template${params}`) as { template: string }
      currentTemplate.value = data.template
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取模板失败'
    }
  }

  async function switchActiveVersion(name: string, version: string) {
    try {
      await request.put(`/admin/prompts/${name}/active`, { version })
      await fetchPrompts()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '切换版本失败'
      throw e
    }
  }

  async function registerVersion(name: string, template: string, version?: string, activate = false) {
    try {
      await request.post(`/admin/prompts/${name}/versions`, { template, version, activate })
      await fetchPrompts()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '注册版本失败'
      throw e
    }
  }

  async function startABTest(name: string, canary_version: string, traffic_fraction = 0.1) {
    try {
      await request.post(`/admin/prompts/${name}/ab-test`, { canary_version, traffic_fraction })
      await fetchPrompts()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '启动A/B测试失败'
      throw e
    }
  }

  async function stopABTest(name: string) {
    try {
      await request.delete(`/admin/prompts/${name}/ab-test`)
      await fetchPrompts()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '停止A/B测试失败'
      throw e
    }
  }

  async function fetchABResults(name: string) {
    try {
      const data = await request.get(`/admin/prompts/${name}/ab-results`) as { versions: Record<string, ABResultSummary> }
      abResults.value = data.versions
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取A/B结果失败'
    }
  }

  return {
    prompts,
    currentTemplate,
    abResults,
    loading,
    error,
    fetchPrompts,
    fetchTemplate,
    switchActiveVersion,
    registerVersion,
    startABTest,
    stopABTest,
    fetchABResults,
  }
})