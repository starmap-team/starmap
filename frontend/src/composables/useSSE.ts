/**
 * SSE composable with exponential backoff and polling fallback.
 *
 * Usage:
 *   const { connected, disconnect } = useSSE('/api/v1/dashboard/realtime', {
 *     onMessage: (event) => { ... },
 *     onError: (err) => { ... },
 *   })
 */
import { ref, onUnmounted } from 'vue'

export interface UseSSEOptions {
  /** Called for each SSE message (named events dispatch by event type) */
  onMessage: (event: MessageEvent) => void
  /** Called on connection errors after all retries exhausted or on fatal errors */
  onError?: (err: Event) => void
  /** Base delay in ms for exponential backoff (default: 1000) */
  baseDelay?: number
  /** Maximum delay cap in ms (default: 30000) */
  maxDelay?: number
  /** Maximum retry attempts before giving up (default: 10) */
  maxRetries?: number
  /** Consecutive failures before switching to polling fallback (default: 3) */
  pollThreshold?: number
  /** Polling interval in ms when SSE is unavailable (default: 5000) */
  pollInterval?: number
  /** URL for polling fallback (defaults to url + '-poll') */
  pollUrl?: string
}

export function useSSE(url: string, options: UseSSEOptions) {
  const {
    onMessage,
    onError,
    baseDelay = 1000,
    maxDelay = 30000,
    maxRetries = 10,
    pollThreshold = 3,
    pollInterval = 5000,
    pollUrl,
  } = options

  const connected = ref(false)
  const mode = ref<'sse' | 'polling' | 'disconnected'>('disconnected')

  let eventSource: EventSource | null = null
  let retryCount = 0
  let consecutiveFailures = 0
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let disposed = false

  // ── SSE connection ──

  function connectSSE() {
    if (disposed) return

    // Close existing connection
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }

    try {
      eventSource = new EventSource(url)
      mode.value = 'sse'

      eventSource.onopen = () => {
        connected.value = true
        retryCount = 0
        consecutiveFailures = 0
      }

      eventSource.onmessage = (event: MessageEvent) => {
        connected.value = true
        consecutiveFailures = 0
        onMessage(event)
      }

      // Also listen for named events (heartbeat, skill_update, etc.)
      eventSource.addEventListener('skill_update', onMessage)
      eventSource.addEventListener('match_event', onMessage)
      eventSource.addEventListener('graph_update', onMessage)
      eventSource.addEventListener('pipeline_event', onMessage)

      eventSource.onerror = (err: Event) => {
        connected.value = false
        eventSource?.close()
        eventSource = null

        consecutiveFailures++

        // Switch to polling after consecutive failures
        if (consecutiveFailures >= pollThreshold) {
          console.warn(`[useSSE] ${consecutiveFailures} consecutive failures, switching to polling`)
          startPolling()
          return
        }

        // Exponential backoff reconnect
        if (retryCount < maxRetries) {
          const delay = Math.min(baseDelay * Math.pow(2, retryCount), maxDelay)
          retryCount++
          console.warn(`[useSSE] Reconnecting in ${delay}ms (attempt ${retryCount}/${maxRetries})`)
          retryTimer = setTimeout(connectSSE, delay)
        } else {
          console.error('[useSSE] Max retries reached, attempting polling fallback')
          startPolling()
          onError?.(err)
        }
      }
    } catch {
      // EventSource constructor failed (e.g., invalid URL)
      startPolling()
    }
  }

  // ── Polling fallback ──

  async function pollOnce() {
    if (disposed) return
    try {
      const response = await fetch(pollUrl || `${url}-poll`, {
        headers: { 'Accept': 'application/json' },
      })
      if (response.ok) {
        const data = await response.json()
        connected.value = true
        consecutiveFailures = 0
        // Wrap as MessageEvent-like for consistency
        if (Array.isArray(data)) {
          for (const item of data) {
            onMessage(new MessageEvent('message', {
              data: JSON.stringify(item),
            }))
          }
        } else if (data && typeof data === 'object') {
          onMessage(new MessageEvent('message', {
            data: JSON.stringify(data),
          }))
        }
      }
    } catch {
      consecutiveFailures++
    }
  }

  function startPolling() {
    if (disposed || pollTimer) return
    mode.value = 'polling'
    console.info(`[useSSE] Polling every ${pollInterval}ms`)

    // Close SSE if still open
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }

    // Immediate first poll
    pollOnce()
    pollTimer = setInterval(pollOnce, pollInterval)
  }

  // ── Cleanup ──

  function disconnect() {
    disposed = true

    if (eventSource) {
      eventSource.close()
      eventSource = null
    }

    if (retryTimer) {
      clearTimeout(retryTimer)
      retryTimer = null
    }

    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }

    connected.value = false
    mode.value = 'disconnected'
  }

  // Auto-cleanup on component unmount
  onUnmounted(disconnect)

  // Start connection
  connectSSE()

  return {
    connected,
    mode,
    disconnect,
  }
}
