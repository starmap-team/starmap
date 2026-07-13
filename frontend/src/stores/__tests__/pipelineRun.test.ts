/**
 * PipelineRun store tests — covers fetchStatus, fetchRuns, fetchRunDetail,
 * triggerPipeline, retryStage, resumeRun, cancelRun, fetchStages,
 * fetchDataQuality, fetchDataSources, SSE event handlers, initial state,
 * error handling, and loading state
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePipelineRunStore } from '../pipelineRun'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('usePipelineRunStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // ── 1. Initial state ──

  it('should have correct initial state', () => {
    const store = usePipelineRunStore()
    expect(store.pipelineStatus).toBeNull()
    expect(store.runs).toEqual([])
    expect(store.stages).toEqual([])
    expect(store.dataQuality).toBeNull()
    expect(store.dataSources).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
    expect(store.liveEvents).toEqual([])
    expect(store.qualityAlerts).toEqual([])
    expect(store.milestones).toEqual([])
    expect(store.recentExtractions).toEqual([])
  })

  // ── 2. fetchStatus action ──

  it('should fetch pipeline status and set state', async () => {
    const request = (await import('@/api/request')).default
    const mockStatus = {
      is_running: true,
      current_run: { id: 'run-1', run_type: 'full', status: 'running', started_at: '2024-01-01', completed_at: null, stages: [], total_records: 0, new_records: 0, updated_records: 0, quality_score: 0, error_log: null, selected_stages: null },
      last_run: null,
      run_counts: { full: 5, incremental: 10 },
      active_data_sources: 3,
      today_crawl_volume: 100,
      success_rate: 0.95,
      avg_quality_score: 0.85,
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockStatus)

    const store = usePipelineRunStore()
    await store.fetchStatus()

    expect(store.pipelineStatus).toBeTruthy()
    expect(store.pipelineStatus!.is_running).toBe(true)
    expect(store.pipelineStatus!.active_data_sources).toBe(3)
    expect(store.loading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/pipeline/status')
  })

  // ── 3. fetchRuns action ──

  it('should fetch runs and populate runs list', async () => {
    const request = (await import('@/api/request')).default
    const mockRuns = [
      { id: 'run-1', run_type: 'full', status: 'completed', started_at: '2024-01-01', completed_at: '2024-01-01', stages: [], total_records: 100, new_records: 50, updated_records: 50, quality_score: 0.9, error_log: null, selected_stages: null },
    ]
    vi.mocked(request.get).mockResolvedValueOnce(mockRuns)

    const store = usePipelineRunStore()
    await store.fetchRuns()

    expect(store.runs).toHaveLength(1)
    expect(store.runs[0].id).toBe('run-1')
    expect(store.loading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/pipeline/runs')
  })

  // ── 4. triggerPipeline action ──

  it('should trigger pipeline and refresh status', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({})
    // fetchStatus after trigger
    vi.mocked(request.get).mockResolvedValueOnce({ is_running: true, current_run: null, last_run: null, run_counts: {}, active_data_sources: 0, today_crawl_volume: 0, success_rate: 0, avg_quality_score: 0 })
    // fetchStages after trigger
    vi.mocked(request.get).mockResolvedValueOnce({ stages: [] })

    const store = usePipelineRunStore()
    await store.triggerPipeline('full')

    expect(request.post).toHaveBeenCalledWith('/pipeline/trigger', { run_type: 'full' })
    expect(store.loading).toBe(false)
  })

  it('should trigger pipeline with selected stages', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({})
    vi.mocked(request.get).mockResolvedValueOnce({ is_running: false, current_run: null, last_run: null, run_counts: {}, active_data_sources: 0, today_crawl_volume: 0, success_rate: 0, avg_quality_score: 0 })
    vi.mocked(request.get).mockResolvedValueOnce({ stages: [] })

    const store = usePipelineRunStore()
    await store.triggerPipeline('incremental', ['crawl', 'clean'])

    expect(request.post).toHaveBeenCalledWith('/pipeline/trigger', {
      run_type: 'incremental',
      selected_stages: ['crawl', 'clean'],
    })
  })

  // ── 5. cancelRun action ──

  it('should cancel a run and return true on success', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({})
    // fetchStatus after cancel
    vi.mocked(request.get).mockResolvedValueOnce({ is_running: false, current_run: null, last_run: null, run_counts: {}, active_data_sources: 0, today_crawl_volume: 0, success_rate: 0, avg_quality_score: 0 })

    const store = usePipelineRunStore()
    const result = await store.cancelRun('run-1')

    expect(result).toBe(true)
    expect(request.post).toHaveBeenCalledWith('/pipeline/runs/run-1/cancel')
    expect(store.loading).toBe(false)
  })

  it('should return false and set error when cancelRun fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockRejectedValueOnce(new Error('Cancel failed'))

    const store = usePipelineRunStore()
    const result = await store.cancelRun('run-1')

    expect(result).toBe(false)
    expect(store.error).toBe('Cancel failed')
    expect(store.loading).toBe(false)
  })

  // ── 6. SSE event handlers ──

  it('should handle pipeline events and auto-refresh on status change', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce({ stages: [] }) // fetchStages
    vi.mocked(request.get).mockResolvedValueOnce({ is_running: true, current_run: null, last_run: null, run_counts: {}, active_data_sources: 0, today_crawl_volume: 0, success_rate: 0, avg_quality_score: 0 }) // fetchStatus

    const store = usePipelineRunStore()
    store.handlePipelineEvent({ stage: 'crawl', status: 'running', progress: 0.5, message: 'Crawling...' })

    expect(store.liveEvents).toHaveLength(1)
    expect(store.liveEvents[0].stage).toBe('crawl')
    // Should auto-refresh stages and status
    expect(request.get).toHaveBeenCalled()
  })

  it('should cap liveEvents at 50', () => {
    const store = usePipelineRunStore()
    for (let i = 0; i < 55; i++) {
      store.handlePipelineEvent({ stage: `stage-${i}`, status: 'completed', progress: 1, message: `Done ${i}` })
    }
    expect(store.liveEvents).toHaveLength(50)
  })

  it('should handle quality alert events', () => {
    const store = usePipelineRunStore()
    store.handleQualityAlert({ id: 'qa-1', severity: 'warning', message: 'Low quality', metric: 'completeness', value: 0.5, threshold: 0.8, timestamp: '2024-01-01T00:00:00Z' })

    expect(store.qualityAlerts).toHaveLength(1)
    expect(store.qualityAlerts[0].id).toBe('qa-1')
  })

  it('should populate created_at from timestamp in quality alert', () => {
    const store = usePipelineRunStore()
    store.handleQualityAlert({ id: 'qa-2', severity: 'error', message: 'Bad data', metric: 'accuracy', value: 0.3, threshold: 0.7, timestamp: '2024-01-01T12:00:00Z' })

    expect(store.qualityAlerts[0].created_at).toBe('2024-01-01T12:00:00Z')
  })

  it('should cap qualityAlerts at 50', () => {
    const store = usePipelineRunStore()
    for (let i = 0; i < 55; i++) {
      store.handleQualityAlert({ id: `qa-${i}`, severity: 'warning', message: `Alert ${i}`, metric: 'test', value: 0.5, threshold: 0.8, timestamp: '2024-01-01' })
    }
    expect(store.qualityAlerts).toHaveLength(50)
  })

  it('should handle milestone events', () => {
    const store = usePipelineRunStore()
    store.handleMilestone({ type: 'records', count: 1000, source: 'crawl', message: '1000 records processed', timestamp: '2024-01-01' })

    expect(store.milestones).toHaveLength(1)
    expect(store.milestones[0].count).toBe(1000)
  })

  it('should handle extraction complete events', () => {
    const store = usePipelineRunStore()
    store.handleExtractionComplete({ jd_id: 'jd-1', source: 'boss', skills_count: 10, duration_ms: 500, quality_score: 0.9, timestamp: '2024-01-01' })

    expect(store.recentExtractions).toHaveLength(1)
    expect(store.recentExtractions[0].jd_id).toBe('jd-1')
  })

  // ── 7. Error handling ──

  it('should set error when fetchStatus fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Server error'))

    const store = usePipelineRunStore()
    await store.fetchStatus()

    expect(store.error).toBe('Server error')
    expect(store.loading).toBe(false)
  })

  it('should set error when fetchRuns fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Network error'))

    const store = usePipelineRunStore()
    await store.fetchRuns()

    expect(store.error).toBe('Network error')
    expect(store.loading).toBe(false)
  })

  it('should set error when triggerPipeline fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockRejectedValueOnce(new Error('Trigger failed'))

    const store = usePipelineRunStore()
    await store.triggerPipeline()

    expect(store.error).toBe('Trigger failed')
    expect(store.loading).toBe(false)
  })

  // ── 8. Loading state ──

  it('should toggle loading state during fetchStatus', async () => {
    const request = (await import('@/api/request')).default
    let resolvePromise: (value: unknown) => void
    const pendingPromise = new Promise(resolve => { resolvePromise = resolve })
    vi.mocked(request.get).mockReturnValueOnce(pendingPromise as any)

    const store = usePipelineRunStore()
    const actionPromise = store.fetchStatus()

    expect(store.loading).toBe(true)

    resolvePromise!({ is_running: false })
    await actionPromise

    expect(store.loading).toBe(false)
  })

  // ── fetchRunDetail ──

  it('should fetch run detail', async () => {
    const request = (await import('@/api/request')).default
    const mockRun = { id: 'run-1', run_type: 'full', status: 'completed', started_at: '2024-01-01', completed_at: '2024-01-01', stages: [], total_records: 100, new_records: 50, updated_records: 50, quality_score: 0.9, error_log: null, selected_stages: null }
    vi.mocked(request.get).mockResolvedValueOnce(mockRun)

    const store = usePipelineRunStore()
    const result = await store.fetchRunDetail('run-1')

    expect(result).toBeTruthy()
    expect(result!.id).toBe('run-1')
    expect(request.get).toHaveBeenCalledWith('/pipeline/runs/run-1')
  })

  it('should return null when fetchRunDetail fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Not found'))

    const store = usePipelineRunStore()
    const result = await store.fetchRunDetail('nonexistent')

    expect(result).toBeNull()
    expect(store.error).toBeTruthy()
  })

  // ── fetchDataQuality ──

  it('should fetch data quality and merge metrics with alerts', async () => {
    const request = (await import('@/api/request')).default
    const mockQuality = {
      metrics: { overall_score: 0.85, completeness: 0.9, accuracy: 0.8, freshness_hours: 24, duplicate_rate: 0.05, total_records: 1000, valid_records: 950, consistency: 0.9, timeliness: 0.85, trend: [] },
      alerts: [{ id: 'a1', severity: 'warning', message: 'Low freshness', metric: 'freshness', value: 48, threshold: 24, timestamp: '2024-01-01' }],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockQuality)

    const store = usePipelineRunStore()
    await store.fetchDataQuality()

    expect(store.dataQuality).toBeTruthy()
    expect(store.dataQuality!.overall_score).toBe(0.85)
    expect(store.dataQuality!.alerts).toHaveLength(1)
  })

  // ── retryStage ──

  it('should retry a failed stage', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({})
    vi.mocked(request.get).mockResolvedValueOnce({ stages: [] }) // fetchStages
    vi.mocked(request.get).mockResolvedValueOnce({ is_running: false, current_run: null, last_run: null, run_counts: {}, active_data_sources: 0, today_crawl_volume: 0, success_rate: 0, avg_quality_score: 0 }) // fetchStatus

    const store = usePipelineRunStore()
    await store.retryStage('run-1', 'crawl')

    expect(request.post).toHaveBeenCalledWith('/pipeline/runs/run-1/retry', { stage_name: 'crawl' })
  })

  // ── resumeRun ──

  it('should resume a run', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({})
    vi.mocked(request.get).mockResolvedValueOnce({ stages: [] }) // fetchStages
    vi.mocked(request.get).mockResolvedValueOnce({ is_running: true, current_run: null, last_run: null, run_counts: {}, active_data_sources: 0, today_crawl_volume: 0, success_rate: 0, avg_quality_score: 0 }) // fetchStatus

    const store = usePipelineRunStore()
    await store.resumeRun('run-1')

    expect(request.post).toHaveBeenCalledWith('/pipeline/runs/run-1/resume')
  })
})
