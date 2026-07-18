/**
 * Review store — Phase 23 review-workflow state machine on the client.
 *
 * Wraps the unified admin review queue:
 * - GET  /admin/review-items       list pending positions + skills
 * - POST /admin/review/{t}/{id}/{action}  submit/approve/reject/unpublish
 *
 * Admin only — store does not enforce auth (caller's responsibility).
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

export type ReviewStatus = 'draft' | 'pending_review' | 'approved' | 'rejected'
export type ReviewEntityType = 'position' | 'skill'

export interface ReviewItem {
  entity_type: ReviewEntityType
  entity_id: string
  name: string
  industry: string | null
  review_status: ReviewStatus
  created_by: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  submitted_at: string | null
  rejection_reason: string | null
  created_at: string | null
}

export interface ReviewStats {
  position: number
  skill: number
  [key: string]: number
}

export const useReviewStore = defineStore('review', () => {
  const items = ref<ReviewItem[]>([])
  const stats = ref<ReviewStats>({ position: 0, skill: 0 })
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchItems(
    entityType?: ReviewEntityType,
    status?: ReviewStatus,
    limit = 50,
  ): Promise<ReviewItem[]> {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, string | number> = { limit }
      if (entityType) params.entity_type = entityType
      if (status) params.status = status
      const data = (await request.get('/admin/review-items', { params })) as {
        items: ReviewItem[]
        total: number
      }
      items.value = data.items ?? []
      return items.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取审核队列失败'
      if (import.meta.env.DEV) console.error('[Review] Failed to fetch items:', e)
      items.value = []
      return []
    } finally {
      loading.value = false
    }
  }

  async function fetchStats(): Promise<ReviewStats> {
    try {
      const data = (await request.get('/admin/review-stats')) as ReviewStats
      stats.value = data
      return stats.value
    } catch (e) {
      if (import.meta.env.DEV) console.error('[Review] Failed to fetch stats:', e)
      return stats.value
    }
  }

  async function submit(entityType: ReviewEntityType, entityId: string): Promise<ReviewItem> {
    return request.post<ReviewItem>(`/admin/review/${entityType}/${entityId}/submit`, {})
  }

  async function approve(
    entityType: ReviewEntityType,
    entityId: string,
    reason?: string,
  ): Promise<ReviewItem> {
    return request.post<ReviewItem>(`/admin/review/${entityType}/${entityId}/approve`, {
      reason: reason ?? null,
    })
  }

  async function reject(
    entityType: ReviewEntityType,
    entityId: string,
    reason: string,
  ): Promise<ReviewItem> {
    return request.post<ReviewItem>(`/admin/review/${entityType}/${entityId}/reject`, {
      reason,
    })
  }

  async function unpublish(
    entityType: ReviewEntityType,
    entityId: string,
    reason: string,
  ): Promise<ReviewItem> {
    return request.post<ReviewItem>(`/admin/review/${entityType}/${entityId}/unpublish`, {
      reason,
    })
  }

  /** Optimistically remove an item from the local list (after admin action). */
  function removeLocal(entityId: string) {
    items.value = items.value.filter((i) => i.entity_id !== entityId)
  }

  return {
    items,
    stats,
    loading,
    error,
    fetchItems,
    fetchStats,
    submit,
    approve,
    reject,
    unpublish,
    removeLocal,
  }
})
