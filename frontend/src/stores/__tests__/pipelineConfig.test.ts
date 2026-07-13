/**
 * PipelineConfig store tests — covers fetchSchedules, createSchedule,
 * updateSchedule, deleteSchedule, triggerSchedule, fetchConfig, updateConfig,
 * initial state, and error handling
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePipelineConfigStore } from '../pipelineConfig'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

// Mock pipelineRun store for cross-store dependency in triggerSchedule
vi.mock('../pipelineRun', () => ({
  usePipelineRunStore: vi.fn(() => ({
    fetchStatus: vi.fn().mockResolvedValue(undefined),
  })),
}))

describe('usePipelineConfigStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // ── 1. Initial state ──

  it('should have correct initial state', () => {
    const store = usePipelineConfigStore()
    expect(store.schedules).toEqual([])
    expect(store.config).toBeNull()
    expect(store.scheduleLoading).toBe(false)
    expect(store.configLoading).toBe(false)
    expect(store.error).toBeNull()
  })

  // ── 2. fetchSchedules ──

  it('should fetch schedules', async () => {
    const request = (await import('@/api/request')).default
    const mockSchedules = [
      { id: 'sch-1', name: 'Daily Crawl', cron_expression: '0 2 * * *', run_type: 'incremental', selected_stages: null, enabled: true, last_run_at: null, next_run_at: '2024-01-02T02:00:00Z', created_at: '2024-01-01' },
    ]
    vi.mocked(request.get).mockResolvedValueOnce(mockSchedules)

    const store = usePipelineConfigStore()
    await store.fetchSchedules()

    expect(store.schedules).toHaveLength(1)
    expect(store.schedules[0].name).toBe('Daily Crawl')
    expect(store.scheduleLoading).toBe(false)
  })

  // ── 3. fetchConfig ──

  it('should fetch pipeline config', async () => {
    const request = (await import('@/api/request')).default
    const mockConfig = { stage_timeout: 300, worker_concurrency: 4, crawl_concurrency: 2, retry_max: 3, retry_backoff: 30 }
    vi.mocked(request.get).mockResolvedValueOnce(mockConfig)

    const store = usePipelineConfigStore()
    await store.fetchConfig()

    expect(store.config).toBeTruthy()
    expect(store.config!.stage_timeout).toBe(300)
    expect(store.configLoading).toBe(false)
  })

  // ── 4. createSchedule ──

  it('should create a schedule and refresh list', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({})
    const mockSchedules = [
      { id: 'sch-1', name: 'New Schedule', cron_expression: '0 3 * * *', run_type: 'full', selected_stages: null, enabled: true, last_run_at: null, next_run_at: null, created_at: '2024-01-01' },
    ]
    vi.mocked(request.get).mockResolvedValueOnce(mockSchedules)

    const store = usePipelineConfigStore()
    await store.createSchedule({ name: 'New Schedule', cron_expression: '0 3 * * *', run_type: 'full', selected_stages: null, enabled: true })

    expect(request.post).toHaveBeenCalledWith('/pipeline/schedules', { name: 'New Schedule', cron_expression: '0 3 * * *', run_type: 'full', selected_stages: null, enabled: true })
    expect(store.scheduleLoading).toBe(false)
  })

  // ── 5. updateSchedule ──

  it('should update a schedule and refresh list', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.put).mockResolvedValueOnce({})
    vi.mocked(request.get).mockResolvedValueOnce([])

    const store = usePipelineConfigStore()
    await store.updateSchedule('sch-1', { name: 'Updated', cron_expression: '0 4 * * *', run_type: 'incremental', selected_stages: null, enabled: false })

    expect(request.put).toHaveBeenCalledWith('/pipeline/schedules/sch-1', { name: 'Updated', cron_expression: '0 4 * * *', run_type: 'incremental', selected_stages: null, enabled: false })
    expect(store.scheduleLoading).toBe(false)
  })

  // ── 6. deleteSchedule ──

  it('should delete a schedule and refresh list', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.delete).mockResolvedValueOnce({})
    vi.mocked(request.get).mockResolvedValueOnce([])

    const store = usePipelineConfigStore()
    await store.deleteSchedule('sch-1')

    expect(request.delete).toHaveBeenCalledWith('/pipeline/schedules/sch-1')
    expect(store.scheduleLoading).toBe(false)
  })

  // ── 7. triggerSchedule ──

  it('should trigger a schedule and refresh list + status', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({})
    vi.mocked(request.get).mockResolvedValueOnce([]) // fetchSchedules

    const store = usePipelineConfigStore()
    await store.triggerSchedule('sch-1')

    expect(request.post).toHaveBeenCalledWith('/pipeline/schedules/sch-1/trigger')
    expect(store.scheduleLoading).toBe(false)
  })

  // ── 8. updateConfig ──

  it('should update pipeline config', async () => {
    const request = (await import('@/api/request')).default
    const updatedConfig = { stage_timeout: 600, worker_concurrency: 8, crawl_concurrency: 4, retry_max: 5, retry_backoff: 60 }
    vi.mocked(request.put).mockResolvedValueOnce(updatedConfig)

    const store = usePipelineConfigStore()
    await store.updateConfig({ stage_timeout: 600 })

    expect(request.put).toHaveBeenCalledWith('/pipeline/config', { stage_timeout: 600 })
    expect(store.config!.stage_timeout).toBe(600)
    expect(store.configLoading).toBe(false)
  })

  // ── 9. Error handling ──

  it('should set error when fetchSchedules fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Schedule error'))

    const store = usePipelineConfigStore()
    await store.fetchSchedules()

    expect(store.error).toBe('Schedule error')
    expect(store.scheduleLoading).toBe(false)
  })

  it('should set error when fetchConfig fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Config error'))

    const store = usePipelineConfigStore()
    await store.fetchConfig()

    expect(store.error).toBe('Config error')
    expect(store.configLoading).toBe(false)
  })

  it('should set error when createSchedule fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockRejectedValueOnce(new Error('Create failed'))

    const store = usePipelineConfigStore()
    await store.createSchedule({ name: 'Test', cron_expression: '0 0 * * *', run_type: 'full', selected_stages: null, enabled: true })

    expect(store.error).toBe('Create failed')
    expect(store.scheduleLoading).toBe(false)
  })

  it('should set error when deleteSchedule fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.delete).mockRejectedValueOnce(new Error('Delete failed'))

    const store = usePipelineConfigStore()
    await store.deleteSchedule('sch-1')

    expect(store.error).toBe('Delete failed')
    expect(store.scheduleLoading).toBe(false)
  })

  it('should set error when triggerSchedule fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockRejectedValueOnce(new Error('Trigger schedule failed'))

    const store = usePipelineConfigStore()
    await store.triggerSchedule('sch-1')

    expect(store.error).toBe('Trigger schedule failed')
    expect(store.scheduleLoading).toBe(false)
  })

  it('should set error when updateConfig fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.put).mockRejectedValueOnce(new Error('Update config failed'))

    const store = usePipelineConfigStore()
    await store.updateConfig({ stage_timeout: 600 })

    expect(store.error).toBe('Update config failed')
    expect(store.configLoading).toBe(false)
  })
})
