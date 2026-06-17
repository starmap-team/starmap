import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 管理后台 store */
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
      const resp = await fetch('/api/v1/admin/sources')
      const data = await resp.json()
      sources.value = data.items ?? []
    } finally {
      loading.value = false
    }
  }

  async function fetchAuditQueue() {
    const resp = await fetch('/api/v1/admin/audit-queue')
    const data = await resp.json()
    auditQueue.value = data.items ?? []
  }

  async function approveAudit(id: number) {
    await fetch(`/api/v1/admin/audit/${id}/approve`, { method: 'POST' })
    auditQueue.value = auditQueue.value.filter((i) => i.id !== id)
  }

  async function rejectAudit(id: number) {
    await fetch(`/api/v1/admin/audit/${id}/reject`, { method: 'POST' })
    auditQueue.value = auditQueue.value.filter((i) => i.id !== id)
  }

  async function resetToDemo() {
    await fetch('/api/v1/admin/reset-demo', { method: 'POST' })
  }

  return { sources, auditQueue, loading, fetchSources, fetchAuditQueue, approveAudit, rejectAudit, resetToDemo }
})
