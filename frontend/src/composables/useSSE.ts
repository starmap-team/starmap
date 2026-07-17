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
import { API_BASE } from '@/config/apiBase'

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
  /**
   * Phase 1 D-09: Optional event-type-specific handlers map.
   * If provided, useSSE will dispatch event to matching handler based on event.type
   * before falling back to onMessage.
   */
  storeHandlers?: Record<string, (data: unknown) => void>
  /** Interval in ms to retry SSE connection while in polling mode (default: 60000) */
  sseRetryInterval?: number
}

/**
 * P0-F2 fix: silent refresh for SSE connections.
 * EventSource cannot set Authorization headers, so when the access token
 * expires (15 min), SSE reconnects fail with 401. This function attempts
 * a silent refresh using the stored refresh token before reconnecting.
 */
async function silentRefreshForSSE(): Promise<string | null> {
  const rt = localStorage.getItem('starmap_refresh_token')
  if (!rt) return null

  try {
    const apiBase = API_BASE
    const resp = await fetch(`${apiBase}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    })
    if (!resp.ok) return null
    const data = await resp.json()
    const newAccess: string | undefined = data?.access_token
    if (newAccess) {
      localStorage.setItem('starmap_access_token', newAccess)
      return newAccess
    }
  } catch {
    // Network error or parse failure — cannot refresh
  }
  return null
}

export function useSSE(url: string, options: UseSSEOptions) {
  const {
    onMessage,
    onError,
    baseDelay = 1000, // initial backoff delay in ms — doubled on each retry
    maxDelay = 30000,
    maxRetries = 10, // max SSE reconnect attempts before polling fallback
    pollThreshold = 3,
    pollInterval = 5000,
    pollUrl,
    storeHandlers,  // Phase 1 D-09: optional event-type dispatch
    sseRetryInterval = 60000, // retry SSE while polling every 60s
  } = options

  const connected = ref(false)
  const mode = ref<'sse' | 'polling' | 'disconnected'>('disconnected')

  let eventSource: EventSource | null = null
  let retryCount = 0
  let consecutiveFailures = 0
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let sseRetryTimer: ReturnType<typeof setInterval> | null = null
  let disposed = false
  let refreshingToken = false  // P0-F2: guard against parallel refreshes

  // ── SSE connection ──

  function connectSSE() {
    if (disposed) return

    // Close existing connection
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }

    try {
      // LOOP-02: Append JWT token as query parameter for SSE auth
      // EventSource API doesn't support custom headers, so token goes in URL
      // FIX-03: Read from starmap_access_token (primary) with legacy fallback
      const token = localStorage.getItem('starmap_access_token') || localStorage.getItem('starmap_token') || localStorage.getItem('token')
      const separator = url.includes('?') ? '&' : '?'
      const authedUrl = token ? `${url}${separator}token=${encodeURIComponent(token)}` : url
      eventSource = new EventSource(authedUrl)
      mode.value = 'sse'

      eventSource.onopen = () => {
        connected.value = true
        retryCount = 0
        consecutiveFailures = 0
        // If we were polling, stop polling and switch back to SSE mode
        if (pollTimer) {
          clearInterval(pollTimer)
          pollTimer = null
        }
        if (sseRetryTimer) {
          clearInterval(sseRetryTimer)
          sseRetryTimer = null
        }
        mode.value = 'sse'
      }

      eventSource.onmessage = (event: MessageEvent) => {
        connected.value = true
        consecutiveFailures = 0
        // Phase 1 D-09: dispatch to storeHandlers if event has type field
        if (storeHandlers) {
          try {
            const data = JSON.parse(event.data)
            const handler = storeHandlers[data?.type]
            if (handler) {
              handler(data?.data ?? data)
            }
          } catch { /* ignore parse errors */ }
        }
        onMessage(event)
      }

      // Also listen for named events (heartbeat, skill_update, etc.)
      eventSource.addEventListener('skill_update', onMessage)
      eventSource.addEventListener('match_event', onMessage)
      eventSource.addEventListener('graph_update', onMessage)

      // Phase 1 SSE-01/02/03: 监听新增的 3 种 named events
      if (storeHandlers) {
        eventSource.addEventListener('pipeline_update', (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data)
            storeHandlers['pipeline_update']?.(data?.data ?? data)
          } catch { /* ignore */ }
        })
        eventSource.addEventListener('quality_alert', (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data)
            storeHandlers.quality_alert?.(data?.data ?? data)
          } catch { /* ignore */ }
        })
        eventSource.addEventListener('data_milestone', (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data)
            storeHandlers.data_milestone?.(data?.data ?? data)
          } catch { /* ignore */ }
        })
        eventSource.addEventListener('extraction_complete', (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data)
            storeHandlers.extraction_complete?.(data?.data ?? data)
          } catch { /* ignore */ }
        })
      }

      eventSource.onerror = () => {
        connected.value = false
        eventSource?.close()
        eventSource = null

        consecutiveFailures++

        // P0-F2 fix: on first failure, attempt silent token refresh.
        // EventSource.onerror doesn't expose HTTP status/headers, so we
        // proactively refresh when a refresh token exists. If refresh
        // succeeds, reconnect immediately with the new access token.
        if (consecutiveFailures === 1 && !refreshingToken) {
          const hasRefreshToken = !!localStorage.getItem('starmap_refresh_token')
          if (hasRefreshToken) {
            refreshingToken = true
            silentRefreshForSSE().then((newToken) => {
              refreshingToken = false
              if (newToken && !disposed) {
                if (import.meta.env.DEV) console.warn('[useSSE] Token refreshed, reconnecting SSE')
                retryCount = 0
                consecutiveFailures = 0
                connectSSE()
                return
              }
              // Refresh failed — fall through to normal backoff
              handleSSEError()
            })
            return
          }
        }

        handleSSEError()
      }

      function handleSSEError() {
        // Switch to polling after consecutive failures
        if (consecutiveFailures >= pollThreshold) {
          // keep: records SSE→polling fallback for ops debugging
          if (import.meta.env.DEV) console.warn(`[useSSE] ${consecutiveFailures} consecutive failures, switching to polling`)
          startPolling()
          return
        }

        // Exponential backoff reconnect
        if (retryCount < maxRetries) {
          const delay = Math.min(baseDelay * Math.pow(2, retryCount), maxDelay)
          retryCount++
          // keep: records reconnection attempt for ops debugging
          if (import.meta.env.DEV) console.warn(`[useSSE] Reconnecting in ${delay}ms (attempt ${retryCount}/${maxRetries})`)
          retryTimer = setTimeout(connectSSE, delay)
        } else {
          if (import.meta.env.DEV) console.error('[useSSE] Max retries reached, attempting polling fallback')
          startPolling()
          onError?.(new Event('error'))
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
      // LOOP-02: Add Authorization header for polling fetch auth
      // FIX-03: Read from starmap_access_token (primary) with legacy fallback
      const token = localStorage.getItem('starmap_access_token') || localStorage.getItem('starmap_token') || localStorage.getItem('token')
      const headers: Record<string, string> = {
        'Accept': 'application/json',
      }
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }
      const response = await fetch(pollUrl || `${url}-poll`, { headers })
      if (response.ok) {
        const data = await response.json()
        connected.value = true
        consecutiveFailures = 0
        // Wrap as MessageEvent-like for consistency
        if (Array.isArray(data)) {
          for (const item of data) {
            // Dispatch to storeHandlers by item.type (mimics SSE named event behavior)
            if (storeHandlers && item?.type && storeHandlers[item.type]) {
              storeHandlers[item.type](item?.data ?? item)
            }
            onMessage(new MessageEvent('message', {
              data: JSON.stringify(item),
            }))
          }
        } else if (data && typeof data === 'object') {
          if (storeHandlers && data?.type && storeHandlers[data.type]) {
            storeHandlers[data.type](data?.data ?? data)
          }
          onMessage(new MessageEvent('message', {
            data: JSON.stringify(data),
          }))
        }
      } else if (response.status === 401) {
        // P0-F2: polling also gets 401 — try silent refresh
        const newToken = await silentRefreshForSSE()
        if (newToken) {
          // Retry this poll immediately with new token
          headers['Authorization'] = `Bearer ${newToken}`
          const retryResp = await fetch(pollUrl || `${url}-poll`, { headers })
          if (retryResp.ok) {
            const retryData = await retryResp.json()
            connected.value = true
            consecutiveFailures = 0
            if (Array.isArray(retryData)) {
              for (const item of retryData) {
                if (storeHandlers && item?.type && storeHandlers[item.type]) {
                  storeHandlers[item.type](item?.data ?? item)
                }
                onMessage(new MessageEvent('message', { data: JSON.stringify(item) }))
              }
            } else if (retryData && typeof retryData === 'object') {
              if (storeHandlers && retryData?.type && storeHandlers[retryData.type]) {
                storeHandlers[retryData.type](retryData?.data ?? retryData)
              }
              onMessage(new MessageEvent('message', { data: JSON.stringify(retryData) }))
            }
          }
        }
      }
    } catch {
      consecutiveFailures++
    }
  }

  function startPolling() {
    if (disposed || pollTimer) return
    mode.value = 'polling'
    // keep: records SSE→polling fallback for ops debugging
    if (import.meta.env.DEV) console.warn(`[useSSE] Polling every ${pollInterval}ms`)

    // Close SSE if still open
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }

    // Immediate first poll
    pollOnce()
    pollTimer = setInterval(pollOnce, pollInterval)

    // Periodically attempt to reconnect to SSE while polling
    if (!sseRetryTimer) {
      sseRetryTimer = setInterval(() => {
        if (disposed || mode.value === 'sse') return
        if (import.meta.env.DEV) console.warn('[useSSE] Attempting SSE reconnection from polling mode')
        // Reset retry state so connectSSE starts fresh
        retryCount = 0
        consecutiveFailures = 0
        connectSSE()
      }, sseRetryInterval)
    }
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

    if (sseRetryTimer) {
      clearInterval(sseRetryTimer)
      sseRetryTimer = null
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
