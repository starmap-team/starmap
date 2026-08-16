/**
 * D-07: admin 一键审核接入 M10 endpoint 契约测试。
 *
 * 验证 QualityDashboard 调用的 audit.approveAudit/rejectAudit 经由
 * ``@/stores/audit`` 打 ``/admin/audit/${id}/approve`` / ``reject``（M10 既有）。
 * 本测试断言 store 行为 + 路由契约，不新建审核 endpoint。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockPost = vi.fn()
const mockGet = vi.fn()
vi.mock('@/api/request', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: () => Promise.resolve({}),
    delete: () => Promise.resolve({}),
  },
}))

describe(' D-07 admin 一键审核接入 M10 endpoint', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const { useAuditStore } = await import('@/stores/audit')
    setActivePinia(createPinia())
    // store lazily
    void useAuditStore
  })

  it('approveAudit 调用 M10 /admin/audit/{id}/approve', async () => {
    mockPost.mockResolvedValueOnce({ success: true })
    const { useAuditStore } = await import('@/stores/audit')
    const store = useAuditStore()
    await store.approveAudit(42)
    expect(mockPost).toHaveBeenCalledWith('/admin/audit/42/approve')
  })

  it('rejectAudit 调用 M10 /admin/audit/{id}/reject', async () => {
    mockPost.mockResolvedValueOnce({ success: true })
    const { useAuditStore } = await import('@/stores/audit')
    const store = useAuditStore()
    await store.rejectAudit(99)
    expect(mockPost).toHaveBeenCalledWith('/admin/audit/99/reject')
  })
})
