/**
 * DataDashboard realtime sync — SSE + periodic refresh + clock tick (Phase 7 D round 3)
 * Sets up SSE connection with targeted incremental refresh, conditional polling, and clock tick.
 * Caller must mount/unmount within a setup() context. All timers are torn down on scope exit.
 */
import { onMounted, onUnmounted, ref, watch, type Ref } from 'vue'
import { useSSE } from '@/composables/useSSE'
import type { useDashboardStore } from '@/stores/dashboard'
import type { RealtimeEvent } from '@/stores/dashboard'

type DashboardStore = ReturnType<typeof useDashboardStore>

const REFRESH_DEBOUNCE_MS = 500
const OVERVIEW_REFRESH_MS = 30_000
const CLOCK_TICK_MS = 1_000

/** Targeted refresh mapping: event type → store fetch methods to call */
const EVENT_REFRESH_MAP: Readonly<Record<RealtimeEvent['type'], (keyof DashboardStore)[]>> = {
  skill_update:       ['fetchOverview', 'fetchDistribution'],
  graph_update:       ['fetchOverview', 'fetchDistribution'],
  match_event:        ['fetchOverview'],
  pipeline_event:     ['fetchPipelineTimeline'],
  extraction:         ['fetchOverview'],
}

export type ConnectionState = 'connecting' | 'connected' | 'polling' | 'disconnected'

export interface DashboardRealtimeSyncApi {
  clockTick: Ref<number>
  sseConnected: Ref<boolean>
  connectionState: Ref<ConnectionState>
}

export function useDashboardRealtimeSync(
  store: DashboardStore,
  sseUrl: string,
  pollUrl: string,
): DashboardRealtimeSyncApi {
  const clockTick: Ref<number> = ref(0)
  const sseConnected: Ref<boolean> = ref(false)
  const connectionState: Ref<ConnectionState> = ref('connecting')

  let refreshTimer: ReturnType<typeof setInterval> | null = null
  let clockTimer: ReturnType<typeof setInterval> | null = null

  // Debounced refresh per target — avoids duplicate calls when multiple events
  // map to the same fetch method within the debounce window
  const pendingRefreshTimers = new Map<string, ReturnType<typeof setTimeout>>()

  function scheduleTargetedRefresh(fetchMethods: (keyof DashboardStore)[]): void {
    for (const method of fetchMethods) {
      if (!pendingRefreshTimers.has(method)) {
        const timer = setTimeout(() => {
          pendingRefreshTimers.delete(method)
          const fn = store[method]
          if (typeof fn === 'function') {
            void (fn as () => Promise<void>)()
          }
        }, REFRESH_DEBOUNCE_MS)
        pendingRefreshTimers.set(method, timer)
      }
    }
  }

  function clearPendingRefreshTimers(): void {
    for (const timer of pendingRefreshTimers.values()) {
      clearTimeout(timer)
    }
    pendingRefreshTimers.clear()
  }

  function startPollingInterval(): void {
    stopPollingInterval()
    refreshTimer = setInterval(() => {
      void store.fetchOverview()
    }, OVERVIEW_REFRESH_MS)
  }

  function stopPollingInterval(): void {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  onMounted(async () => {
    await store.fetchAll()

    // Start in connecting state; polling starts as fallback
    connectionState.value = 'connecting'
    startPollingInterval()

    const { connected, mode } = useSSE(sseUrl, {
      onMessage: (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as RealtimeEvent
          if (data?.type) {
            store.addRealtimeEvent(data)
            const targets = EVENT_REFRESH_MAP[data.type]
            if (targets) {
              scheduleTargetedRefresh(targets)
            }
          }
        } catch {
          // Heartbeat or non-JSON; ignore
        }
      },
      onError: () => {
        if (import.meta.env.DEV) console.warn('[Dashboard] SSE connection failed, using polling fallback')
      },
      pollUrl,
    })

    watch(connected, (val) => {
      sseConnected.value = val
      store.sseConnected = val
    }, { immediate: true })

    watch(mode, (val) => {
      if (val === 'sse') {
        connectionState.value = 'connected'
        stopPollingInterval()
      } else if (val === 'polling') {
        connectionState.value = 'polling'
        startPollingInterval()
      } else {
        connectionState.value = 'disconnected'
        stopPollingInterval()
      }
    }, { immediate: true })

    clockTimer = setInterval(() => {
      clockTick.value++
    }, CLOCK_TICK_MS)
  })

  onUnmounted(() => {
    stopPollingInterval()
    if (clockTimer) {
      clearInterval(clockTimer)
      clockTimer = null
    }
    clearPendingRefreshTimers()
  })

  return { clockTick, sseConnected, connectionState }
}
