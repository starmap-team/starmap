import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDataSourceStore } from '../datasource'
import { useAuditStore, type AuditItem } from '../audit'
import type { DataSourceDetail } from '@/types/datasource'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('useDataSourceStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should have correct initial state', () => {
    const store = useDataSourceStore()
    expect(store.sources).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('should store source configs', () => {
    const store = useDataSourceStore()
    const mockSources: DataSourceDetail[] = [
      { id: '1', name: 'BOSS直聘', authority_score: 0.8, source_type: 'crawler', status: 'active', last_crawl_at: '', total_records: 0, valid_records: 0, duplicate_rate: 0, avg_quality_score: 0, daily_crawl_volume: [] },
    ]
    store.sources = mockSources
    expect(store.sources).toHaveLength(1)
    expect(store.sources[0].name).toBe('BOSS直聘')
  })
})

describe('useAuditStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should have correct initial state', () => {
    const store = useAuditStore()
    expect(store.auditQueue).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('should store audit items', () => {
    const store = useAuditStore()
    const mockItems: AuditItem[] = [
      { id: 1, type: 'skill', name: 'Python', trust: 0.85, status: 'pending' },
      { id: 2, type: 'position', name: 'Backend Dev', trust: 0.72, status: 'approved' },
    ]
    store.auditQueue = mockItems
    expect(store.auditQueue).toHaveLength(2)
    expect(store.auditQueue[0].name).toBe('Python')
  })

  it('should batch approve and remove items from queue', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce([
      { id: 1, type: 'skill', name: 'Python', trust: 0.85, status: 'approved' },
      { id: 3, type: 'skill', name: 'Go', trust: 0.70, status: 'approved' },
    ])

    const store = useAuditStore()
    store.auditQueue = [
      { id: 1, type: 'skill', name: 'Python', trust: 0.85, status: 'pending' },
      { id: 2, type: 'position', name: 'Engineer', trust: 0.60, status: 'pending' },
      { id: 3, type: 'skill', name: 'Go', trust: 0.70, status: 'pending' },
    ] as AuditItem[]

    await store.batchAudit([1, 3], 'approve')

    expect(request.post).toHaveBeenCalledWith('/admin/audit/batch', {
      item_ids: [1, 3],
      action: 'approve',
    })
    // Items 1 and 3 should be removed; item 2 remains
    expect(store.auditQueue).toHaveLength(1)
    expect(store.auditQueue[0].id).toBe(2)
  })
})

describe('useDataSourceStore — health & sync', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should fetch health data', async () => {
    const request = (await import('@/api/request')).default
    const mockHealth = {
      sources: [
        { id: '1', name: 'BOSS直聘', status: 'active', last_crawl_at: null, total_records: 100, recent_run_status: null },
      ],
      total_sources: 1,
      active_sources: 1,
      error_sources: 0,
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockHealth)

    const store = useDataSourceStore()
    const result = await store.fetchHealth()

    expect(result).toEqual(mockHealth)
    expect(store.health).toEqual(mockHealth)
    expect(request.get).toHaveBeenCalledWith('/datasources/health')
  })

  it('should handle fetchHealth error', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Server error'))

    const store = useDataSourceStore()
    const result = await store.fetchHealth()

    expect(result).toBeNull()
    expect(store.error).toBe('Server error')
  })

  it('should trigger sync and refresh source detail', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({ run_id: 'abc', status: 'running' })
    vi.mocked(request.get).mockResolvedValueOnce({ id: '1', name: 'BOSS直聘', authority_score: 0.8, source_type: 'crawler', status: 'active', last_crawl_at: '', total_records: 0, valid_records: 0, duplicate_rate: 0, avg_quality_score: 0 } as DataSourceDetail)

    const store = useDataSourceStore()
    const result = await store.triggerSync('1')

    expect(result).toBe(true)
    expect(request.post).toHaveBeenCalledWith('/datasources/1/sync')
  })
})