/**
 * DataDashboard realtime sync — SSE + periodic refresh + clock tick (Phase 7 D round 3)
 * Sets up SSE connection with debounced overview refresh, periodic polling, and clock tick.
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

const REFRESH_TRIGGERING_TYPES: ReadonlySet<RealtimeEvent['type']> = new Set<RealtimeEvent['type']>([
  'skill_update',
  'graph_update',
  'pipeline_event',
  'extraction',
])

export interface DashboardRealtimeSyncApi {
  clockTick: Ref<number>
  sseConnected: Ref<boolean>
}

export function useDashboardRealtimeSync(
  store: DashboardStore,
  sseUrl: string,
  pollUrl: string,
): DashboardRealtimeSyncApi {
  const clockTick: Ref<number> = ref(0)
  const sseConnected: Ref<boolean> = ref(false)

  let refreshTimer: ReturnType<typeof setInterval> | null = null
  let clockTimer: ReturnType<typeof setInterval> | null = null
  let sseRefreshTimer: ReturnType<typeof setTimeout> | null = null

  function scheduleSSEOverviewRefresh(): void {
    if (sseRefreshTimer) clearTimeout(sseRefreshTimer)
    sseRefreshTimer = setTimeout(() => {
      void store.fetchOverview()
    }, REFRESH_DEBOUNCE_MS)
  }

  onMounted(async () => {
    await store.fetchAll()

    const { connected } = useSSE(sseUrl, {
      onMessage: (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as RealtimeEvent
          if (data?.type) {
            store.addRealtimeEvent(data)
            if (REFRESH_TRIGGERING_TYPES.has(data.type)) {
              scheduleSSEOverviewRefresh()
            }
          }
        } catch {
          // Heartbeat or non-JSON; ignore
        }
      },
      onError: () => {
        // ponytail: keep console.warn for ops debugging of SSE→polling fallback
        console.warn('[Dashboard] SSE connection failed, using polling fallback')
      },
      pollUrl,
    })

    watch(connected, (val) => {
      sseConnected.value = val
      store.sseConnected = val
    }, { immediate: true })

    refreshTimer = setInterval(() => {
      void store.fetchOverview()
    }, OVERVIEW_REFRESH_MS)

    clockTimer = setInterval(() => {
      clockTick.value++
    }, CLOCK_TICK_MS)
  })

  onUnmounted(() => {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
    if (clockTimer) {
      clearInterval(clockTimer)
      clockTimer = null
    }
    if (sseRefreshTimer) {
      clearTimeout(sseRefreshTimer)
      sseRefreshTimer = null
    }
  })

  return { clockTick, sseConnected }
}
