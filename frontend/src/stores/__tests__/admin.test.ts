import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAdminStore, type AuditItem } from '../admin'
import type { DataSourceDetail } from '@/types/datasource'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('useAdminStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should have correct initial state', () => {
    const store = useAdminStore()
    expect(store.sources).toEqual([])
    expect(store.auditQueue).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('should store audit items', () => {
    const store = useAdminStore()
    const mockItems: AuditItem[] = [
      { id: 1, type: 'skill', name: 'Python', trust: 0.85, status: 'pending' },
      { id: 2, type: 'position', name: 'Backend Dev', trust: 0.72, status: 'approved' },
    ]
    store.auditQueue = mockItems
    expect(store.auditQueue).toHaveLength(2)
    expect(store.auditQueue[0].name).toBe('Python')
  })

  it('should store source configs', () => {
    const store = useAdminStore()
    const mockSources: DataSourceDetail[] = [
      { id: '1', name: 'BOSS直聘', authority_score: 0.8, source_type: 'crawler', status: 'active', last_crawl_at: '', total_records: 0, valid_records: 0, duplicate_rate: 0, avg_quality_score: 0, daily_crawl_volume: [] },
    ]
    store.sources = mockSources
    expect(store.sources).toHaveLength(1)
    expect(store.sources[0].name).toBe('BOSS直聘')
  })
})
