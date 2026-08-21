/**
 * Review store — review-workflow state machine on the client.
 *
 * Wraps the unified admin review queue:
 * - GET /admin/review-items list pending positions + skills
 * - POST /admin/review/{t}/{id}/{action} submit/approve/reject/unpublish
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
  name_cn: string | null
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
 // P2 fix (functional-review 2026-08-13): 显式声明后端 review_service 实际
 // 返回的扁平键（此前仅有 index signature，类型隐藏漂移 —— 模板用
 // position_approved/skill_pending_review/evolution_pending 等键而类型不感知）。
  position_pending_review: number
  position_approved: number
  position_rejected: number
  skill_pending_review: number
  skill_approved: number
  skill_rejected: number
  evolution_pending: number
  total_count: number
  daily_volume: number
  avg_daily_count: number
  [key: string]: number
}

export const useReviewStore = defineStore('review', () => {
  const items = ref<ReviewItem[]>([])
  const stats = ref<ReviewStats>({
    position: 0,
    skill: 0,
    position_pending_review: 0,
    position_approved: 0,
    position_rejected: 0,
    skill_pending_review: 0,
    skill_approved: 0,
    skill_rejected: 0,
    evolution_pending: 0,
    total_count: 0,
    daily_volume: 0,
    avg_daily_count: 0,
  })
  const loading = ref(false)
  const error = ref<string | null>(null)
  // 2026-08-21: 当前筛选条件下的真实总数（后端 count，非 limit 截断值）
  const filterTotal = ref(0)

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
      // 2026-08-21: 保存真实筛选总数（后端已改为 count，非 limit 截断值）
      filterTotal.value = data.total ?? items.value.length
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
    filterTotal,
    fetchItems,
    fetchStats,
    submit,
    approve,
    reject,
    unpublish,
    removeLocal,
  }
})
