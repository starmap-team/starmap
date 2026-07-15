/**
 * Dashboard store tests — covers fetchOverview, fetchTrends, fetchDistribution,
 * fetchAll, addRealtimeEvent, initial state, error handling, and loading state
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDashboardStore } from '../dashboard'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('useDashboardStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // ── 1. Initial state ──

  it('should have correct initial state', () => {
    const store = useDashboardStore()
    expect(store.overview).toBeNull()
    expect(store.sourceDistribution).toEqual([])
    expect(store.skillDomains).toEqual([])
    expect(store.qualityTrends).toEqual([])
    expect(store.realtimeEvents).toEqual([])
    expect(store.pipelineTimeline).toEqual([])
    expect(store.emergingSkills).toEqual([])
    expect(store.sseConnected).toBe(false)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  // ── 2. fetchOverview action ──

  it('should fetch overview and map backend fields to frontend DashboardOverview', async () => {
	    const request = (await import('@/api/request')).default
	    const mockOverview = {
	      total_nodes: 1000,
	      total_edges: 5000,
	      total_domains: 10,
	      total_positions: 50,
	      total_skills: 200,
	      trust_score: 0.85,
	      hallucination_rate: 0.05,
	      total_extractions: 500,
	      data_volume: 300,
	      today_extractions: 15,
	      pipeline_status: 'running',
	      active_data_sources: 5,
	      weekly_new_nodes: 100,
	      stale: false,
	      stale_since: null,
	      timestamp: 1700000000,
	    }
	    vi.mocked(request.get).mockResolvedValueOnce(mockOverview)

	    const store = useDashboardStore()
	    await store.fetchOverview()

	    expect(store.overview).toBeTruthy()
	    expect(store.overview!.total_nodes).toBe(1000)
	    expect(store.overview!.trust_score).toBe(0.85)
	    expect(store.overview!.data_volume).toBe(300)
	    expect(store.overview!.active_data_sources).toBe(5)
	    expect(store.overview!.pipeline_status).toBe('running')
	    expect(store.overview!.today_extractions).toBe(15)
	    expect(store.overview!.stale).toBe(false)
	    expect(store.loading).toBe(false)
	    expect(request.get).toHaveBeenCalledWith('/dashboard/overview')
	  })

  it('should handle missing fields with defaults in fetchOverview', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce({})

    const store = useDashboardStore()
    await store.fetchOverview()

    expect(store.overview).toBeTruthy()
    expect(store.overview!.total_nodes).toBe(0)
	    expect(store.overview!.trust_score).toBe(0)
    expect(store.overview!.pipeline_status).toBe('idle')
  })

  // ── 3. fetchTrends action ──

  it('should fetch trends and map to QualityTrend', async () => {
    const request = (await import('@/api/request')).default
    const mockTrends = {
      period: '7d',
      data_points: [
        { date: '2024-01-01', total_records: 100, new_records: 10, quality_score: 0.9, extractions: 5 },
        { date: '2024-01-02', total_records: 110, new_records: 10, quality_score: 0.92, extractions: 8 },
      ],
      summary: {},
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockTrends)

    const store = useDashboardStore()
    await store.fetchTrends()

    expect(store.qualityTrends).toHaveLength(2)
    expect(store.qualityTrends[0].date).toBe('2024-01-01')
    expect(store.qualityTrends[0].quality_score).toBe(0.9)
    expect(store.qualityTrends[0].trust_score).toBe(0.9) // reuse quality as trust proxy
    expect(store.qualityTrends[0].crawl_volume).toBe(5)
    expect(request.get).toHaveBeenCalledWith('/dashboard/trends')
  })

  it('should set qualityTrends to empty on fetch failure', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Network error'))

    const store = useDashboardStore()
    await store.fetchTrends()

    expect(store.qualityTrends).toEqual([])
  })

  // ── 4. fetchDistribution action ──

  it('should fetch distribution and map source + domain data', async () => {
    const request = (await import('@/api/request')).default
    const mockDistribution = {
      source_distribution: [
        { name: 'Boss直聘', total_records: 500, authority_score: 0.9 },
        { name: '拉勾', total_records: 300, authority_score: 0.8 },
      ],
      domain_distribution: [
        { name: 'Backend', count: 50 },
        { name: 'Frontend', value: 30 },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockDistribution)

    const store = useDashboardStore()
    await store.fetchDistribution()

    expect(store.sourceDistribution).toHaveLength(2)
    expect(store.sourceDistribution[0].name).toBe('Boss直聘')
    expect(store.sourceDistribution[0].count).toBe(500)
    expect(store.sourceDistribution[0].trust).toBe(0.9)
    expect(store.skillDomains).toHaveLength(2)
    expect(store.skillDomains[0].name).toBe('Backend')
    expect(store.skillDomains[0].value).toBe(50)
    expect(store.skillDomains[1].value).toBe(30) // uses value field when count is undefined
    expect(request.get).toHaveBeenCalledWith('/dashboard/distribution')
  })

  it('should set sourceDistribution to empty on fetch failure', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Server error'))

    const store = useDashboardStore()
    await store.fetchDistribution()

    expect(store.sourceDistribution).toEqual([])
  })

  // ── 5. fetchAll action ──

  it('should fetch all dashboard data in parallel', async () => {
    const request = (await import('@/api/request')).default
    // Mock all 6 endpoints called by fetchAll
    vi.mocked(request.get).mockResolvedValueOnce({ total_nodes: 100, total_edges: 500, total_domains: 5, total_positions: 20, total_skills: 100, trust_score: 0.8, hallucination_rate: 0.02, total_extractions: 200, data_volume: 50, today_extractions: 5, active_data_sources: 3, pipeline_status: 'idle', weekly_new_nodes: 10, stale: false, stale_since: null, timestamp: 1700000000 }) // fetchOverview
    vi.mocked(request.get).mockResolvedValueOnce({ period: '7d', data_points: [], summary: {} }) // fetchTrends
    vi.mocked(request.get).mockResolvedValueOnce({ source_distribution: [], domain_distribution: [] }) // fetchDistribution
    vi.mocked(request.get).mockResolvedValueOnce({ source_distribution: [], domain_distribution: [] }) // fetchSkillDomains (calls fetchDistribution)
    vi.mocked(request.get).mockResolvedValueOnce([]) // fetchEmergingSkills
    vi.mocked(request.get).mockResolvedValueOnce({ stages: [] }) // fetchPipelineTimeline

    const store = useDashboardStore()
    await store.fetchAll()

    expect(store.overview).toBeTruthy()
    expect(store.loading).toBe(false)
  })

  // ── 6. addRealtimeEvent action ──

  it('should add a realtime event and prepend to events list', () => {
    const store = useDashboardStore()
    const event = {
      id: 'evt-1',
      type: 'skill_update' as const,
      title: 'Python updated',
      detail: 'New skill added',
      timestamp: '2024-01-01T00:00:00Z',
    }
    store.addRealtimeEvent(event)

    expect(store.realtimeEvents).toHaveLength(1)
    expect(store.realtimeEvents[0].id).toBe('evt-1')
  })

  it('should prepend events and cap at 100', () => {
    const store = useDashboardStore()

    // Add 101 events
    for (let i = 0; i < 101; i++) {
      store.addRealtimeEvent({
        id: `evt-${i}`,
        type: 'skill_update',
        title: `Event ${i}`,
        detail: 'Detail',
        timestamp: new Date().toISOString(),
      })
    }

    expect(store.realtimeEvents).toHaveLength(100)
    // Most recent event should be first (prepended)
    expect(store.realtimeEvents[0].id).toBe('evt-100')
  })

  // ── 7. Error handling ──

  it('should set error when fetchOverview fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Server unavailable'))

    const store = useDashboardStore()
    await store.fetchOverview()

    expect(store.error).toBe('Server unavailable')
    expect(store.loading).toBe(false)
  })

  // ── 8. Loading state ──

  it('should toggle loading state during fetchOverview', async () => {
    const request = (await import('@/api/request')).default
    let resolvePromise: (value: unknown) => void
    const pendingPromise = new Promise(resolve => { resolvePromise = resolve })
    vi.mocked(request.get).mockReturnValueOnce(pendingPromise as any)

    const store = useDashboardStore()
    const actionPromise = store.fetchOverview()

    expect(store.loading).toBe(true)

    resolvePromise!({ total_nodes: 0 })
    await actionPromise

    expect(store.loading).toBe(false)
  })

  // ── fetchEmergingSkills ──

  it('should fetch emerging skills', async () => {
    const request = (await import('@/api/request')).default
    const mockSkills = [
      { skill_name: 'Rust', trend: 'rising', confidence: 0.9, frequency: 50, growth_rate: 0.3, first_seen: '2024-01-01', domains: ['backend'] },
    ]
    vi.mocked(request.get).mockResolvedValueOnce(mockSkills)

    const store = useDashboardStore()
    await store.fetchEmergingSkills()

    expect(store.emergingSkills).toHaveLength(1)
    expect(store.emergingSkills[0].skill_name).toBe('Rust')
  })

  it('should set emergingSkills to empty on fetch failure', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Not found'))

    const store = useDashboardStore()
    await store.fetchEmergingSkills()

    expect(store.emergingSkills).toEqual([])
  })

  // ── fetchPipelineTimeline ──

  it('should fetch pipeline timeline', async () => {
    const request = (await import('@/api/request')).default
    const mockTimeline = {
      stages: [
        { stage: 'crawl', status: 'completed', started_at: '2024-01-01', completed_at: '2024-01-01', records_processed: 100, progress: 1.0 },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockTimeline)

    const store = useDashboardStore()
    await store.fetchPipelineTimeline()

    expect(store.pipelineTimeline).toHaveLength(1)
    expect(store.pipelineTimeline[0].stage).toBe('crawl')
  })

  it('should set pipelineTimeline to empty on fetch failure', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Error'))

    const store = useDashboardStore()
    await store.fetchPipelineTimeline()

    expect(store.pipelineTimeline).toEqual([])
  })
})
