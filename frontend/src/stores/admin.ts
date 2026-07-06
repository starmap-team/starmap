import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

export interface SourceConfig {
  id: string
  name: string
  authority_score: number
  source_type: string
  status: string
  total_records: number
  valid_records: number
  duplicate_rate: number
  avg_quality_score: number
  config: Record<string, any>
}

export interface AuditItem {
  id: number
  type: 'position' | 'skill'
  name: string
  trust: number
  status: 'pending' | 'approved' | 'rejected'
}

export const useAdminStore = defineStore('admin', () => {
  const sources = ref<SourceConfig[]>([])
  const auditQueue = ref<AuditItem[]>([])
  const loading = ref(false)

  async function fetchSources() {
    loading.value = true
    try {
      const data = await request.get('/datasources') as any
      sources.value = Array.isArray(data) ? data : (data.items ?? [])
    } finally {
      loading.value = false
    }
  }

  async function updateSource(sourceId: string, payload: { authority_score?: number; status?: string; config?: Record<string, any> }) {
    await request.put(`/datasources/${sourceId}`, payload)
  }

  async function fetchAuditQueue() {
    try {
      const data = await request.get('/admin/review-queue')
      auditQueue.value = (data as any).items ?? []
    } catch (e) {
      console.error('[Admin] Failed to fetch audit queue:', e)
      auditQueue.value = []
    }
  }

  async function approveAudit(id: number) {
    await request.post(`/admin/audit/${id}/approve`)
    auditQueue.value = auditQueue.value.filter((i) => i.id !== id)
  }

  async function rejectAudit(id: number) {
    await request.post(`/admin/audit/${id}/reject`)
    auditQueue.value = auditQueue.value.filter((i) => i.id !== id)
  }

  async function updateAuditItem(id: number, data: { name?: string; trust?: number }) {
    await request.put(`/admin/review-queue/${id}`, data)
    // Update local state
    const item = auditQueue.value.find(i => i.id === id)
    if (item) {
      if (data.name !== undefined) item.name = data.name
      if (data.trust !== undefined) item.trust = data.trust
    }
  }

  async function resetToDemo() {
    await request.post('/admin/seed/reset')
  }

  return { sources, auditQueue, loading, fetchSources, updateSource, fetchAuditQueue, approveAudit, rejectAudit, updateAuditItem, resetToDemo }
})
