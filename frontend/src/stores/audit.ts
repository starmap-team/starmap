/**
 * Audit queue store — extracted from datasource.ts (Phase 7 admin domain split).
 * Manages the review/audit queue for admin panel.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

import { useResponseValidation } from '@/validation/useResponseValidation'
import adminSchema from '../../../starmap-contracts/schemas/admin.schema.json'

// PLAN-014: 契约响应校验 (DEV warn 不阻断)
const { validateResponse: validateAdmin } = useResponseValidation()

export interface AuditItem {
  id: number
  type: 'position' | 'skill'
  name: string
  trust: number
  status: 'pending' | 'approved' | 'rejected'
}

interface AuditQueueResponse {
  items: AuditItem[]
}

export const useAuditStore = defineStore('audit', () => {
  const auditQueue = ref<AuditItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchAuditQueue() {
    loading.value = true
    error.value = null
    try {
      const data = validateAdmin(
        await request.get('/admin/review-queue') as AuditQueueResponse,
        adminSchema, '/admin/review-queue', 'AuditQueueResponse',
      ) as AuditQueueResponse
      auditQueue.value = data.items ?? []
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取审核队列失败'
      if (import.meta.env.DEV) console.error('[Audit] Failed to fetch audit queue:', e)
      auditQueue.value = []
    } finally {
      loading.value = false
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
    const item = auditQueue.value.find((i) => i.id === id)
    if (item) {
      if (data.name !== undefined) item.name = data.name
      if (data.trust !== undefined) item.trust = data.trust
    }
  }

  async function batchAudit(ids: number[], action: 'approve' | 'reject') {
    const data = validateAdmin(
        await request.post('/admin/audit/batch', { item_ids: ids, action }) as AuditItem[],
        adminSchema, '/admin/audit/batch', 'AuditItem',
      ) as AuditItem[]
    // Remove processed items from queue
    const processedIds = new Set(ids)
    auditQueue.value = auditQueue.value.filter((i) => !processedIds.has(i.id))
    return data
  }

  return {
    auditQueue,
    loading,
    error,
    fetchAuditQueue,
    approveAudit,
    rejectAudit,
    updateAuditItem,
    batchAudit,
  }
})