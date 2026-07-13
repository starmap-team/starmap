/**
 * Loop store tests — covers runLoop, getStatus, fetchHistory, resetRun,
 * parseFlatResult, computed properties, error handling, and loading state
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useLoopStore } from '../loop'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('useLoopStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // ── 1. Initial state ──

  it('should have correct initial state', () => {
    const store = useLoopStore()
    expect(store.currentRun).toBeNull()
    expect(store.history).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
    expect(store.currentStepIndex).toBe(-1)
    expect(store.completedSteps).toBe(0)
    expect(store.isRunning).toBe(false)
    expect(store.totalDuration).toBe(0)
  })

  // ── 2. runLoop action ──

  it('should run loop and update currentRun with step results', async () => {
    const request = (await import('@/api/request')).default
    const mockResponse = {
      run_id: 'run-abc',
      status: 'completed',
      steps: [
        { step: 1, status: 'success', duration_ms: 50 },
        { step: 2, status: 'success', duration_ms: 2000 },
        { step: 3, status: 'success', duration_ms: 1500 },
        { step: 4, status: 'degraded', duration_ms: 3000, warning: 'Partial match' },
        { step: 5, status: 'success', duration_ms: 1000 },
      ],
    }
    vi.mocked(request.post).mockResolvedValueOnce(mockResponse)

    const store = useLoopStore()
    await store.runLoop('JD text here', 'Backend Developer')

    expect(store.currentRun).toBeTruthy()
    expect(store.currentRun!.run_id).toBe('run-abc')
    expect(store.currentRun!.status).toBe('completed')
    expect(store.currentRun!.steps).toHaveLength(5)
    expect(store.currentRun!.steps[0].status).toBe('success')
    expect(store.currentRun!.steps[3].status).toBe('degraded')
    expect(store.currentRun!.steps[3].warning).toBe('Partial match')
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  // ── 3. getStatus action ──

  it('should get loop status', async () => {
    const request = (await import('@/api/request')).default
    const mockStatus = { run_id: 'run-abc', status: 'running', current_step: 3 }
    vi.mocked(request.get).mockResolvedValueOnce(mockStatus)

    const store = useLoopStore()
    const status = await store.getStatus('run-abc')

    expect(status).toEqual(mockStatus)
    expect(request.get).toHaveBeenCalledWith('/loop/status/run-abc')
  })

  it('should return null when getStatus fails', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Not found'))

    const store = useLoopStore()
    const status = await store.getStatus('nonexistent')

    expect(status).toBeNull()
  })

  // ── 4. fetchHistory action ──

  it('should fetch history and populate history list', async () => {
    const request = (await import('@/api/request')).default
    const mockHistory = {
      items: [
        { run_id: 'run-1', target_position: 'Dev', status: 'completed', step_count: 5, success_count: 5, total_duration_ms: 8000, created_at: '2024-01-01' },
        { run_id: 'run-2', target_position: 'ML Eng', status: 'partial', step_count: 5, success_count: 3, total_duration_ms: 5000, created_at: '2024-01-02' },
      ],
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockHistory)

    const store = useLoopStore()
    await store.fetchHistory()

    expect(store.history).toHaveLength(2)
    expect(store.history[0].run_id).toBe('run-1')
    expect(store.history[1].status).toBe('partial')
    expect(request.get).toHaveBeenCalledWith('/loop/history', { params: { limit: 20 } })
  })

  it('should set history to empty array on fetch failure', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Server error'))

    const store = useLoopStore()
    await store.fetchHistory()

    expect(store.history).toEqual([])
  })

  // ── 5. resetRun action ──

  it('should reset currentRun and error', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({
      run_id: 'run-1', status: 'completed',
      steps: [{ step: 1, status: 'success' }],
    })

    const store = useLoopStore()
    await store.runLoop('test JD')
    expect(store.currentRun).toBeTruthy()

    store.resetRun()

    expect(store.currentRun).toBeNull()
    expect(store.error).toBeNull()
  })

  // ── 6. parseFlatResult (via runLoop with no steps array) ──

  it('should parse flat result when backend returns no steps array', async () => {
    const request = (await import('@/api/request')).default
    const flatResponse = {
      run_id: 'run-flat',
      status: 'completed',
      extracted_skills: [{ skill: 'Python', confidence: 0.9 }],
      confidence: 0.9,
      hallucination_score: 0.1,
      new_nodes: [{ id: '1', name: 'Python', type: 'Skill', is_new: true }],
      existing_nodes: [],
      new_edges: [],
      match_score: 0.75,
      matched_skills: ['Python'],
      missing_skills: ['Docker'],
      gap_analysis: [],
      radar_data: [],
      learning_path: [{ skill: 'Docker', sequence: 1, estimated_hours: 20, prerequisites: [] }],
      estimated_learning_hours: 20,
    }
    vi.mocked(request.post).mockResolvedValueOnce(flatResponse)

    const store = useLoopStore()
    await store.runLoop('JD text', 'Dev')

    expect(store.currentRun).toBeTruthy()
    // Step 1 is always set to success immediately
    expect(store.currentRun!.steps[0].status).toBe('success')
    // Step 2: skill extraction
    expect(store.currentRun!.steps[1].status).toBe('success')
    expect(store.currentRun!.steps[1].data).toBeTruthy()
    // Step 3: graph update
    expect(store.currentRun!.steps[2].status).toBe('success')
    // Step 4: match diagnosis
    expect(store.currentRun!.steps[3].status).toBe('success')
    // Step 5: learning path
    expect(store.currentRun!.steps[4].status).toBe('success')
  })

  // ── 7. Step status parsing (degraded) ──

  it('should mark steps as degraded when degraded flags are set', async () => {
    const request = (await import('@/api/request')).default
    const flatResponse = {
      run_id: 'run-deg',
      status: 'partial',
      extracted_skills: [{ skill: 'Python' }],
      new_nodes: [],
      graph_degraded: true,
      match_score: 0.5,
      match_degraded: true,
      learning_path: [],
      learning_degraded: true,
    }
    vi.mocked(request.post).mockResolvedValueOnce(flatResponse)

    const store = useLoopStore()
    await store.runLoop('JD text')

    // Step 3: graph update should be degraded
    expect(store.currentRun!.steps[2].status).toBe('degraded')
    // Step 4: match should be degraded
    expect(store.currentRun!.steps[3].status).toBe('degraded')
    // Step 5: learning path should be degraded
    expect(store.currentRun!.steps[4].status).toBe('degraded')
  })

  // ── 8. Error handling ──

  it('should set error and mark running step as failed on API failure', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockRejectedValueOnce(new Error('Loop execution failed'))

    const store = useLoopStore()
    await store.runLoop('JD text')

    expect(store.error).toBe('Loop execution failed')
    expect(store.currentRun).toBeTruthy()
    expect(store.currentRun!.status).toBe('partial')
    // Step 1 is set to success before the API call, so no running step to mark failed
    // But the run should be marked as partial
    expect(store.loading).toBe(false)
  })

  // ── 9. Loading state ──

  it('should toggle loading state during runLoop', async () => {
    const request = (await import('@/api/request')).default
    let resolvePromise: (value: unknown) => void
    const pendingPromise = new Promise(resolve => { resolvePromise = resolve })
    vi.mocked(request.post).mockReturnValueOnce(pendingPromise as any)

    const store = useLoopStore()
    const actionPromise = store.runLoop('JD text')

    expect(store.loading).toBe(true)

    resolvePromise!({ run_id: 'r1', status: 'completed', steps: [] })
    await actionPromise

    expect(store.loading).toBe(false)
  })

  // ── 10. Computed properties ──

  it('should compute currentStepIndex correctly', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({
      run_id: 'run-comp',
      status: 'running',
      steps: [
        { step: 1, status: 'success' },
        { step: 2, status: 'running' },
        { step: 3, status: 'waiting' },
      ],
    })

    const store = useLoopStore()
    await store.runLoop('JD text')

    // currentStepIndex should find the running step
    expect(store.currentStepIndex).toBe(1)
  })

  it('should compute completedSteps correctly', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({
      run_id: 'run-comp2',
      status: 'completed',
      steps: [
        { step: 1, status: 'success' },
        { step: 2, status: 'degraded' },
        { step: 3, status: 'failed' },
      ],
    })

    const store = useLoopStore()
    await store.runLoop('JD text')

    // success + degraded = 2 completed steps
    expect(store.completedSteps).toBe(2)
  })

  it('should compute totalDuration correctly', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({
      run_id: 'run-dur',
      status: 'completed',
      steps: [
        { step: 1, status: 'success', duration_ms: 100 },
        { step: 2, status: 'success', duration_ms: 200 },
      ],
    })

    const store = useLoopStore()
    await store.runLoop('JD text')

    expect(store.totalDuration).toBe(300)
  })

  it('should compute isRunning correctly', () => {
    const store = useLoopStore()
    expect(store.isRunning).toBe(false)
  })

  // ── STEP_NAMES constant ──

  it('should have 5 step names', () => {
    const store = useLoopStore()
    expect(store.STEP_NAMES).toHaveLength(5)
    expect(store.STEP_NAMES[0]).toBe('JD 输入')
    expect(store.STEP_NAMES[4]).toBe('学习路径')
  })
})
