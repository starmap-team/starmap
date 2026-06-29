import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

export interface SourceConfig {
  id: number
  name: string
  authority_score: number
  source_type: string
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
      const data = await request.get('/admin/sources')
      sources.value = (data as any).items ?? []
    } finally {
      loading.value = false
    }
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

  async function resetToDemo() {
    await request.post('/admin/seed/reset')
  }

  return { sources, auditQueue, loading, fetchSources, fetchAuditQueue, approveAudit, rejectAudit, resetToDemo }
})
