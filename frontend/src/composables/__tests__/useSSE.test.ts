/**
 * useSSE composable tests — covers connection creation, token auth,
 * message handling, error/reconnection, disconnect, polling fallback,
 * and storeHandlers dispatch
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createApp } from 'vue'

// ── Mock EventSource globally ──

const mockEventSourceInstance: any = {
  close: vi.fn(),
  onopen: null as (() => void) | null,
  onmessage: null as ((ev: MessageEvent) => void) | null,
  onerror: null as ((ev: Event) => void) | null,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  url: '',
  readyState: 0,
  withCredentials: false,
} as const

const MockEventSource = vi.fn(() => {
  mockEventSourceInstance.close.mockReset()
  mockEventSourceInstance.onopen = null
  mockEventSourceInstance.onmessage = null
  mockEventSourceInstance.onerror = null
  mockEventSourceInstance.addEventListener.mockReset()
  mockEventSourceInstance.url = ''
  mockEventSourceInstance.readyState = 0
  return mockEventSourceInstance
})

vi.stubGlobal('EventSource', MockEventSource)

// Mock localStorage for token access
vi.stubGlobal('localStorage', {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
})

// Mock fetch for polling fallback
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// Mock console to suppress dev warnings
vi.spyOn(console, 'warn').mockImplementation(() => {})
vi.spyOn(console, 'error').mockImplementation(() => {})

// ── withSetup helper for composables with lifecycle hooks ──

function withSetup<T>(composable: () => T): { result: T; unmount: () => void } {
  let result: T
  const app = createApp({
    setup() {
      result = composable()
      return () => null
    },
  })
  const el = document.createElement('div')
  app.mount(el)
  const unmount = () => app.unmount()
  return { result: result!, unmount }
}

// Import after mocks are set up
import { useSSE } from '../useSSE'

describe('useSSE', () => {
  let unmount: () => void

  beforeEach(() => {
    vi.useFakeTimers()
    MockEventSource.mockClear()
    mockFetch.mockReset()
    vi.mocked(localStorage.getItem).mockReturnValue(null)
  })

  afterEach(() => {
    unmount?.()
    vi.useRealTimers()
  })

  // ── 1. Connection creation ──

  it('should create EventSource with correct URL on init', () => {
    const onMessage = vi.fn()
    const { result, unmount: teardown } = withSetup(() => useSSE('/api/v1/test', { onMessage }))
    unmount = teardown

    expect(MockEventSource).toHaveBeenCalled()
    expect((MockEventSource as any).mock.calls[0][0]).toBe('/api/v1/test')
    expect(result.mode.value).toBe('sse')
  })

  // ── 2. Token in query param ──

  it('should append JWT token as query parameter for SSE auth', () => {
    vi.mocked(localStorage.getItem).mockReturnValue('my-jwt-token')
    const onMessage = vi.fn()

    const { unmount: teardown } = withSetup(() => useSSE('/api/v1/test', { onMessage }))
    unmount = teardown

    expect((MockEventSource as any).mock.calls[0][0]).toBe('/api/v1/test?token=my-jwt-token')
  })

  it('should use & separator when URL already has query params', () => {
    vi.mocked(localStorage.getItem).mockReturnValue('my-token')
    const onMessage = vi.fn()

    const { unmount: teardown } = withSetup(() => useSSE('/api/v1/test?existing=1', { onMessage }))
    unmount = teardown

    expect((MockEventSource as any).mock.calls[0][0]).toBe('/api/v1/test?existing=1&token=my-token')
  })

  it('should not append token when none is stored', () => {
    vi.mocked(localStorage.getItem).mockReturnValue(null)
    const onMessage = vi.fn()

    const { unmount: teardown } = withSetup(() => useSSE('/api/v1/test', { onMessage }))
    unmount = teardown

    expect((MockEventSource as any).mock.calls[0][0]).toBe('/api/v1/test')
  })

  // ── 3. Message handling ──

  it('should call onMessage callback when SSE message received', () => {
    const onMessage = vi.fn()
    const { result, unmount: teardown } = withSetup(() => useSSE('/api/v1/test', { onMessage }))
    unmount = teardown

    // Simulate onmessage callback
    const messageEvent = new MessageEvent('message', { data: '{"type":"test","data":"hello"}' })
    mockEventSourceInstance.onmessage!(messageEvent)

    expect(onMessage).toHaveBeenCalledWith(messageEvent)
    expect(result.connected.value).toBe(true)
  })

  // ── 4. Error handling and reconnection ──

  it('should attempt reconnection with exponential backoff on error', () => {
    const onMessage = vi.fn()
    const onError = vi.fn()
    const { result, unmount: teardown } = withSetup(() =>
      useSSE('/api/v1/test', { onMessage, onError, baseDelay: 100, maxRetries: 5 })
    )
    unmount = teardown

    // Simulate error
    const errorEvent = new Event('error')
    mockEventSourceInstance.onerror!(errorEvent)

    expect(result.connected.value).toBe(false)
    // Should schedule a reconnect (not call onError yet since retries remain)
    expect(onError).not.toHaveBeenCalled()

    // Advance timer for first backoff (100ms)
    vi.advanceTimersByTime(100)
    // Should have created a new EventSource for reconnection
    expect(MockEventSource.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  // ── 5. Disconnect on unmount ──

  it('should close EventSource on disconnect', () => {
    const onMessage = vi.fn()
    const { result, unmount: teardown } = withSetup(() => useSSE('/api/v1/test', { onMessage }))
    unmount = teardown

    result.disconnect()

    expect(mockEventSourceInstance.close).toHaveBeenCalled()
    expect(result.connected.value).toBe(false)
    expect(result.mode.value).toBe('disconnected')
  })

  it('should disconnect on component unmount', () => {
    const onMessage = vi.fn()
    const { unmount: teardown } = withSetup(() => useSSE('/api/v1/test', { onMessage }))

    teardown()

    expect(mockEventSourceInstance.close).toHaveBeenCalled()
  })

  // ── 6. Polling fallback ──

  it('should switch to polling after consecutive failures exceed pollThreshold', () => {
    const onMessage = vi.fn()
    const { result, unmount: teardown } = withSetup(() =>
      useSSE('/api/v1/test', { onMessage, pollThreshold: 2, pollInterval: 1000, baseDelay: 10 })
    )
    unmount = teardown

    // Simulate consecutive errors
    const errorEvent = new Event('error')
    mockEventSourceInstance.onerror!(errorEvent) // failure 1
    mockEventSourceInstance.onerror!(errorEvent) // failure 2

    // After pollThreshold failures, should switch to polling mode
    expect(result.mode.value).toBe('polling')

    // Disconnect to stop the polling interval
    result.disconnect()
  })

  // ── 7. storeHandlers dispatch ──

  it('should dispatch events to storeHandlers based on event type', () => {
    const onMessage = vi.fn()
    const pipelineHandler = vi.fn()
    const storeHandlers = {
      pipeline_update: pipelineHandler,
    }

    const { unmount: teardown } = withSetup(() =>
      useSSE('/api/v1/test', { onMessage, storeHandlers })
    )
    unmount = teardown

    // Simulate SSE message with pipeline_update type
    const messageEvent = new MessageEvent('message', {
      data: JSON.stringify({ type: 'pipeline_update', data: { stage: 'crawl', status: 'running' } }),
    })
    mockEventSourceInstance.onmessage!(messageEvent)

    expect(pipelineHandler).toHaveBeenCalledWith({ stage: 'crawl', status: 'running' })
    expect(onMessage).toHaveBeenCalled()
  })

  it('should register named event listeners for SSE event types', () => {
    const onMessage = vi.fn()
    const storeHandlers = {
      pipeline_update: vi.fn(),
      quality_alert: vi.fn(),
      data_milestone: vi.fn(),
      extraction_complete: vi.fn(),
    }

    const { unmount: teardown } = withSetup(() =>
      useSSE('/api/v1/test', { onMessage, storeHandlers })
    )
    unmount = teardown

    // Should have registered addEventListener for named events
    const addEventListenerCalls = mockEventSourceInstance.addEventListener.mock.calls
    const eventTypes = addEventListenerCalls.map((call: any[]) => call[0])
    expect(eventTypes).toContain('skill_update')
    expect(eventTypes).toContain('match_event')
    expect(eventTypes).toContain('graph_update')
    expect(eventTypes).toContain('pipeline_update')
    expect(eventTypes).toContain('quality_alert')
    expect(eventTypes).toContain('data_milestone')
    expect(eventTypes).toContain('extraction_complete')
  })

  // ── 8. Max retries exhausted ──

  it('should call onError and switch to polling when max retries exhausted', () => {
    const onMessage = vi.fn()
    const onError = vi.fn()
    const { result, unmount: teardown } = withSetup(() =>
      useSSE('/api/v1/test', { onMessage, onError, maxRetries: 1, baseDelay: 10, pollThreshold: 100 })
    )
    unmount = teardown

    // First error: schedules retry
    mockEventSourceInstance.onerror!(new Event('error'))

    // Advance past retry delay
    vi.advanceTimersByTime(10)

    // Second error: max retries reached
    mockEventSourceInstance.onerror!(new Event('error'))

    expect(onError).toHaveBeenCalled()
    expect(result.mode.value).toBe('polling')
  })

  // ── 9. onopen resets counters ──

  it('should reset retry counters on successful connection', () => {
    const onMessage = vi.fn()
    const { result, unmount: teardown } = withSetup(() =>
      useSSE('/api/v1/test', { onMessage, baseDelay: 10, maxRetries: 5 })
    )
    unmount = teardown

    // Simulate open
    mockEventSourceInstance.onopen!()

    expect(result.connected.value).toBe(true)
  })
})
