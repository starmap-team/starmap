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
   * D-09: Optional event-type-specific handlers map.
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
    storeHandlers,  // D-09: optional event-type dispatch
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
  // P1-2 fix (functional-review 2026-08-13): 轮询游标改用最后一次事件时间戳
  // （lastEventTs）。此前依赖 SSE lastEventId（后端 _format_sse 不发送 id: 行，
  // onmessage 也不触发 → 恒为空 → 轮询恒 since=0 重复拉全量）。

  // ── SSE connection ──

  function connectSSE() {
    if (disposed) return

    // Close existing connection
    if (eventSource) {
      eventSource.close()
      eventSource = null
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

    try {
      // LOOP-02: Append JWT token as query parameter for SSE auth
      // EventSource API doesn't support custom headers, so token goes in URL
      const token = localStorage.getItem('starmap_access_token')
      const separator = url.includes('?') ? '&' : '?'
      const authedUrl = token ? `${url}${separator}token=${encodeURIComponent(token)}` : url
      eventSource = new EventSource(authedUrl)
      mode.value = 'sse'

      eventSource.onopen = () => {
        connected.value = true
        const wasDisconnected = consecutiveFailures > 0
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
        // (Fix M1): 重连成功后显示 toast 提示用户
        if (wasDisconnected) {
          try {
            import('element-plus').then(({ ElMessage }) => {
              ElMessage.success('实时推送已恢复')
            })
          } catch { /* ignore */ }
        }
      }

      eventSource.onmessage = (event: MessageEvent) => {
        connected.value = true
        consecutiveFailures = 0
        // D-09: dispatch to storeHandlers if event has type field
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

      // P1-1 fix (functional-review 2026-08-13): 后端真实事件类型无条件注册。
      // 此前 4 种事件监听写在 `if (storeHandlers)` 内，而 useDataDashboard
      // 未传 storeHandlers → 监听器未注册；且后端恒发命名事件（_format_sse
      // 恒带 `event: {type}`），EventSource 默认 onmessage 不触发命名事件，
      // 导致实时事件流 + 定向刷新整体失效。统一走 onMessage（onMessage 内
      // 已含 storeHandlers 分发逻辑），与 skill_update 等历史类型对称。
      eventSource.addEventListener('pipeline_update', onMessage)
      eventSource.addEventListener('quality_alert', onMessage)
      eventSource.addEventListener('data_milestone', onMessage)
      eventSource.addEventListener('extraction_complete', onMessage)

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
    } catch {
      // EventSource constructor failed (e.g., invalid URL)
      startPolling()
    }
  }

  // ── Polling fallback ──

  // P1-2 fix (functional-review 2026-08-13): 轮询游标。此前依赖 lastEventId
  // （SSE onmessage 才更新，且后端 _format_sse 不发送 id: 行 → 恒为空）→
  // 恒 since=0 每次拉全部事件重复叠加。改为跟踪最后一次事件时间戳，作为
  // 下次 since，实现断点续传 + 天然去重。
  let lastEventTs = 0

  async function pollOnce() {
    if (disposed) return
    try {
      // LOOP-02: Add Authorization header for polling fetch auth
      const token = localStorage.getItem('starmap_access_token')
      const headers: Record<string, string> = {
        'Accept': 'application/json',
      }
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }
      const pollUrlWithCursor = (() => {
        const base = pollUrl || `${url}-poll`
        const sinceParam = lastEventTs > 0 ? `since=${lastEventTs}` : ''
        return sinceParam
          ? `${base}${base.includes('?') ? '&' : '?'}${sinceParam}`
          : base
      })()
      const response = await fetch(pollUrlWithCursor, { headers })
      if (response.ok) {
        const data = await response.json()
        connected.value = true
        consecutiveFailures = 0
        // P1-2 fix: 后端 /realtime-poll 返回 { events: [...], poll_interval_ms } 包装，
        // 此前只处理裸数组/裸对象 → 包装结构走 else 分支，item 无 type → 事件
        // 全部静默丢弃（轮询兜底完全失效）。统一解包 events 数组。
        const items: unknown[] = Array.isArray(data)
          ? data
          : Array.isArray((data as { events?: unknown[] })?.events)
            ? (data as { events: unknown[] }).events
            : data && typeof data === 'object' ? [data] : []
        for (const item of items) {
          const typed = item as { type?: string; data?: unknown; timestamp?: number }
          // 推进断点续传游标（后端 timestamp 为 unix float）
          if (typeof typed?.timestamp === 'number' && typed.timestamp > lastEventTs) {
            lastEventTs = typed.timestamp
          }
          // Dispatch to storeHandlers by item.type (mimics SSE named event behavior)
          if (storeHandlers && typed?.type && storeHandlers[typed.type]) {
            storeHandlers[typed.type](typed?.data ?? typed)
          }
          onMessage(new MessageEvent('message', {
            data: JSON.stringify(typed),
          }))
        }
      } else if (response.status === 401) {
        // P0-F2: polling also gets 401 — try silent refresh
        const newToken = await silentRefreshForSSE()
        if (newToken) {
          // Retry this poll immediately with new token
          headers['Authorization'] = `Bearer ${newToken}`
          const retryResp = await fetch(pollUrlWithCursor, { headers })
          if (retryResp.ok) {
            const retryData = await retryResp.json()
            connected.value = true
            consecutiveFailures = 0
            const retryItems: unknown[] = Array.isArray(retryData)
              ? retryData
              : Array.isArray((retryData as { events?: unknown[] })?.events)
                ? (retryData as { events: unknown[] }).events
                : retryData && typeof retryData === 'object' ? [retryData] : []
            for (const item of retryItems) {
              const typed = item as { type?: string; data?: unknown; timestamp?: number }
              if (typeof typed?.timestamp === 'number' && typed.timestamp > lastEventTs) {
                lastEventTs = typed.timestamp
              }
              if (storeHandlers && typed?.type && storeHandlers[typed.type]) {
                storeHandlers[typed.type](typed?.data ?? typed)
              }
              onMessage(new MessageEvent('message', { data: JSON.stringify(typed) }))
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
