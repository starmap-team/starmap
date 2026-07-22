/**
 * Evolution store tests — covers fetchTrends, fetchSnapshots, fetchChangelog,
 * fetchEmergingAlerts, initial state, error handling, and loading state
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useEvolutionStore } from '../evolution'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('useEvolutionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // ── 1. Initial state ──

  it('should have correct initial state', () => {
    const store = useEvolutionStore()
    expect(store.loading).toBe(false)
    expect(store.trendItems).toEqual([])
    expect(store.snapshotsLoading).toBe(false)
    expect(store.snapshots).toEqual([])
    expect(store.changelogLoading).toBe(false)
    expect(store.changelogData).toEqual([])
    expect(store.emergingAlerts).toEqual([])
    expect(store.alertsLoading).toBe(false)
  })

  // ── 2. fetchTrends action ──

  it('should fetch trends and set trendItems', async () => {
    const request = (await import('@/api/request')).default
    const mockTrends = {
      items: [
        { skill_name: 'Rust', trend: 'rising', confidence: 0.9, points: [1, 2, 3], related_positions: ['Dev'] },
        { skill_name: 'Python', trend: 'stable', confidence: 0.95, points: [5, 5, 5], related_positions: ['Dev', 'ML'] },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockTrends)

    const store = useEvolutionStore()
    const result = await store.fetchTrends()

    expect(store.trendItems).toHaveLength(2)
    expect(store.trendItems[0].skill_name).toBe('Rust')
    expect(result.items).toHaveLength(2)
    expect(store.loading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/evolution/trends', { params: undefined })
  })

  it('should pass days parameter to fetchTrends', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce({ items: [] })

    const store = useEvolutionStore()
    await store.fetchTrends(30)

    expect(request.get).toHaveBeenCalledWith('/evolution/trends', { params: { days: 30 } })
  })

  // ── 3. fetchSnapshots action ──

  it('should fetch snapshots and sort by snapshot_date', async () => {
    const request = (await import('@/api/request')).default
    const mockSnapshots = [
      { id: '2', position_name: 'Dev', snapshot_date: '2024-02-01', required_skills: [], source_count: 5 },
      { id: '1', position_name: 'Dev', snapshot_date: '2024-01-01', required_skills: [], source_count: 3 },
    ]
    vi.mocked(request.get).mockResolvedValueOnce(mockSnapshots)

    const store = useEvolutionStore()
    await store.fetchSnapshots()

    expect(store.snapshots).toHaveLength(2)
    // Should be sorted by snapshot_date ascending
    expect(store.snapshots[0].id).toBe('1')
    expect(store.snapshots[1].id).toBe('2')
    expect(store.snapshotsLoading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/evolution/snapshots?limit=50')
  })

  it('should pass custom limit to fetchSnapshots', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce([])

    const store = useEvolutionStore()
    await store.fetchSnapshots(10)

    expect(request.get).toHaveBeenCalledWith('/evolution/snapshots?limit=10')
  })

  it('should handle non-array snapshot response', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce({ not: 'an array' })

    const store = useEvolutionStore()
    await store.fetchSnapshots()

    expect(store.snapshots).toEqual([])
  })

  // ── 4. fetchChangelog action ──

  it('should fetch changelog and set changelogData', async () => {
    const request = (await import('@/api/request')).default
    const mockChangelog = [
      { id: '1', skill_name: 'Python', change_type: 'added', before_value: null, after_value: 'required', confidence: 0.9, detected_at: '2024-01-01' },
    ]
    vi.mocked(request.get).mockResolvedValueOnce(mockChangelog)

    const store = useEvolutionStore()
    await store.fetchChangelog('Python')

    expect(store.changelogData).toHaveLength(1)
    expect(store.changelogData[0].skill_name).toBe('Python')
    expect(store.changelogLoading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/evolution/changelog/Python')
  })

  it('should handle changelog response with items wrapper', async () => {
    const request = (await import('@/api/request')).default
    const mockResponse = {
      items: [
        { id: '2', skill_name: 'Docker', change_type: 'updated', before_value: 'optional', after_value: 'required', confidence: 0.8, detected_at: '2024-02-01' },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockResponse)

    const store = useEvolutionStore()
    await store.fetchChangelog('Docker')

    expect(store.changelogData).toHaveLength(1)
    expect(store.changelogData[0].skill_name).toBe('Docker')
  })

  it('should handle changelog response with changelog wrapper', async () => {
    const request = (await import('@/api/request')).default
    const mockResponse = {
      changelog: [
        { id: '3', skill_name: 'Go', change_type: 'removed', before_value: 'preferred', after_value: null, confidence: 0.7, detected_at: '2024-03-01' },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockResponse)

    const store = useEvolutionStore()
    await store.fetchChangelog('Go')

    expect(store.changelogData).toHaveLength(1)
    expect(store.changelogData[0].skill_name).toBe('Go')
  })

  // UX-04: fetchChangelog identifier parameter tests
  it('should handle fetchChangelog with identifier containing special characters', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce([
      { id: '4', skill_name: 'C++ / Rust', change_type: 'added', before_value: null, after_value: 'required', confidence: 0.85, detected_at: '2024-04-01' },
    ])

    const store = useEvolutionStore()
    await store.fetchChangelog('C++ / Rust')

    expect(store.changelogData).toHaveLength(1)
    expect(store.changelogData[0].skill_name).toBe('C++ / Rust')
    // Verify URL encoding is used
    expect(request.get).toHaveBeenCalledWith('/evolution/changelog/C%2B%2B%20%2F%20Rust')
  })

  it('should handle fetchChangelog with empty identifier', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce([])

    const store = useEvolutionStore()
    await store.fetchChangelog('')

    expect(store.changelogData).toEqual([])
    expect(request.get).toHaveBeenCalledWith('/evolution/changelog/')
  })

  it('should handle fetchChangelog with non-string response', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce(null)

    const store = useEvolutionStore()
    await store.fetchChangelog('test')

    expect(store.changelogData).toEqual([])
  })

  it('should handle fetchChangelog with nested items/changelog in response', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce({
      items: [
        { id: '5', skill_name: 'Nested', change_type: 'updated', before_value: 'old', after_value: 'new', confidence: 0.9, detected_at: '2024-05-01' },
      ],
      changelog: [
        { id: '6', skill_name: 'Changelog', change_type: 'removed', before_value: 'req', after_value: null, confidence: 0.7, detected_at: '2024-05-02' },
      ],
    })

    const store = useEvolutionStore()
    await store.fetchChangelog('test')

    // Should prefer changelog over items when both are present (matches actual code logic)
    expect(store.changelogData).toHaveLength(1)
    expect(store.changelogData[0].skill_name).toBe('Changelog')
  })

  // ── 5. fetchEmergingAlerts action ──

  it('should fetch emerging alerts and set state', async () => {
    const request = (await import('@/api/request')).default
    const mockAlerts = {
      alerts: [
        { skill_name: 'Rust', category: 'language', level: 'emerging', z_score: 2.5, current_frequency: 50, mean_frequency: 20, domains: ['backend'], positions: ['Dev'], alert_message: 'Rust is emerging' },
      ],
      total: 1,
      summary: '1 emerging skill detected',
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockAlerts)

    const store = useEvolutionStore()
    await store.fetchEmergingAlerts()

    expect(store.emergingAlerts).toHaveLength(1)
    expect(store.emergingAlerts[0].skill_name).toBe('Rust')
    expect(store.alertsLoading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/evolution/emerging-alerts', { params: {} })
  })

  it('should pass level parameter to fetchEmergingAlerts', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce({ alerts: [], total: 0, summary: '' })

    const store = useEvolutionStore()
    await store.fetchEmergingAlerts('rising')

    expect(request.get).toHaveBeenCalledWith('/evolution/emerging-alerts', { params: { level: 'rising' } })
  })

  it('should clear alerts on fetchEmergingAlerts failure', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Server error'))

    const store = useEvolutionStore()
    await store.fetchEmergingAlerts()

    expect(store.emergingAlerts).toEqual([])
    expect(store.alertsLoading).toBe(false)
  })

  // ── 6. Error handling ──

  it('should handle fetchTrends error gracefully (finally still resets loading)', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Network error'))

    const store = useEvolutionStore()
    // fetchTrends does not have a catch block, so it will throw
    await expect(store.fetchTrends()).rejects.toThrow('Network error')
    expect(store.loading).toBe(false)
  })

  // ── 7. Loading state ──

  it('should toggle loading state during fetchTrends', async () => {
    const request = (await import('@/api/request')).default
    let resolvePromise: (value: unknown) => void
    const pendingPromise = new Promise(resolve => { resolvePromise = resolve })
    vi.mocked(request.get).mockReturnValueOnce(pendingPromise as any)

    const store = useEvolutionStore()
    const actionPromise = store.fetchTrends()

    expect(store.loading).toBe(true)

    resolvePromise!({ items: [] })
    await actionPromise

    expect(store.loading).toBe(false)
  })

  it('should toggle snapshotsLoading during fetchSnapshots', async () => {
    const request = (await import('@/api/request')).default
    let resolvePromise: (value: unknown) => void
    const pendingPromise = new Promise(resolve => { resolvePromise = resolve })
    vi.mocked(request.get).mockReturnValueOnce(pendingPromise as any)

    const store = useEvolutionStore()
    const actionPromise = store.fetchSnapshots()

    expect(store.snapshotsLoading).toBe(true)

    resolvePromise!([])
    await actionPromise

    expect(store.snapshotsLoading).toBe(false)
  })

  // ── 8. Multiple fetch actions in sequence ──

  it('should handle multiple fetch actions in sequence', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce({ items: [{ skill_name: 'Rust', trend: 'rising', confidence: 0.9, points: [], related_positions: [] }] })
    vi.mocked(request.get).mockResolvedValueOnce([])
    vi.mocked(request.get).mockResolvedValueOnce([{ id: '1', skill_name: 'Python', change_type: 'added', before_value: null, after_value: 'req', confidence: 0.9, detected_at: '2024-01-01' }])
    vi.mocked(request.get).mockResolvedValueOnce({ alerts: [], total: 0, summary: '' })

    const store = useEvolutionStore()
    await store.fetchTrends()
    await store.fetchSnapshots()
    await store.fetchChangelog('Python')
    await store.fetchEmergingAlerts()

    expect(store.trendItems).toHaveLength(1)
    expect(store.snapshots).toEqual([])
    expect(store.changelogData).toHaveLength(1)
    expect(store.emergingAlerts).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.snapshotsLoading).toBe(false)
    expect(store.changelogLoading).toBe(false)
    expect(store.alertsLoading).toBe(false)
  })

  // ── 9. fetchEmergingAlerts level filtering ──

  it('should filter emerging alerts by level', async () => {
    const request = (await import('@/api/request')).default
    const mockAlerts = {
      alerts: [
        { skill_name: 'Rust', category: 'language', level: 'emerging', z_score: 2.5, current_frequency: 50, mean_frequency: 20, domains: ['backend'], positions: ['Dev'], alert_message: 'Rust is emerging' },
        { skill_name: 'Python', category: 'language', level: 'stable', z_score: 0.5, current_frequency: 100, mean_frequency: 95, domains: ['backend', 'data'], positions: ['Dev', 'Data'], alert_message: 'Python is stable' },
      ],
      total: 2,
      summary: '2 skills detected',
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockAlerts)

    const store = useEvolutionStore()
    await store.fetchEmergingAlerts('emerging')

    // Verify the request was made with the level filter
    expect(request.get).toHaveBeenCalledWith('/evolution/emerging-alerts', { params: { level: 'emerging' } })
    // Both alerts are stored (filtering is done by backend)
    expect(store.emergingAlerts).toHaveLength(2)
  })

  it('should handle fetchEmergingAlerts with empty level', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce({ alerts: [], total: 0, summary: '' })

    const store = useEvolutionStore()
    await store.fetchEmergingAlerts()

    // Should call without level parameter
    expect(request.get).toHaveBeenCalledWith('/evolution/emerging-alerts', { params: {} })
  })
})
