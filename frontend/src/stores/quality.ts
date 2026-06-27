import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/api/request'

export interface QualityMetrics {
  precision: number
  recall: number
  f1: number
  warning_level: 'green' | 'yellow' | 'orange' | 'red'
  details: { dimension: string; value: number; threshold: number; status: 'pass' | 'warn' | 'fail' }[]
  total_nodes: number
  total_edges: number
  total_positions: number
  total_skills: number
  avg_confidence: number
  hallucination_rate: number
  pending_review: number
  avg_trust_score: number
  high_trust_ratio: number
  weekly_new_nodes: number
  audit_pass_rate: number
  source_distribution: { name: string; count: number; trust: number }[]
  hallucination_trend: { date: string; rate: number }[]
  trust_distribution: { range: string; count: number }[]
  audit_queue: { id: number; position: string; skill: string; trust: number }[]
}

function defaultMetrics(): QualityMetrics {
  return {
    precision: 0,
    recall: 0,
    f1: 0,
    warning_level: 'red',
    details: [],
    total_nodes: 0,
    total_edges: 0,
    total_positions: 0,
    total_skills: 0,
    avg_confidence: 0,
    hallucination_rate: 0,
    pending_review: 0,
    avg_trust_score: 0,
    high_trust_ratio: 0,
    weekly_new_nodes: 0,
    audit_pass_rate: 1.0,
    source_distribution: [],
    hallucination_trend: [],
    trust_distribution: [],
    audit_queue: [],
  }
}

export const useQualityStore = defineStore('quality', () => {
  const metrics = ref<QualityMetrics | null>(null)
  const loading = ref(false)

  async function fetchQuality() {
    loading.value = true
    try {
      let data: Record<string, unknown>
      try {
        data = (await request.get('/quality/dashboard')) as Record<string, unknown>
      } catch {
        data = (await request.get('/quality/report')) as Record<string, unknown>
      }
      const merged = { ...defaultMetrics() }
      const report = (data as Record<string, unknown>).report as Record<string, unknown> | undefined
      const src = report ?? data
      for (const key of Object.keys(merged)) {
        if (key in src && (src as Record<string, unknown>)[key] !== undefined) {
          (merged as Record<string, unknown>)[key] = (src as Record<string, unknown>)[key]
        }
      }
      for (const key of Object.keys(data)) {
        if (key !== 'report' && key in merged && data[key] !== undefined) {
          (merged as Record<string, unknown>)[key] = data[key]
        }
      }
      metrics.value = merged
    } finally {
      loading.value = false
    }
  }

  const kpiCards = computed(() => {
    if (!metrics.value) return []
    const m = metrics.value
    return [
      { label: '节点总数', value: m.total_nodes.toLocaleString(), color: '#409eff' },
      { label: '平均信任度', value: m.avg_trust_score.toFixed(1), color: '#67c23a' },
      { label: '幻觉率', value: (m.hallucination_rate * 100).toFixed(1) + '%', color: '#e6a23c' },
      { label: '待审核', value: m.pending_review, color: '#f56c6c' },
    ]
  })

  return { metrics, loading, kpiCards, fetchQuality }
})