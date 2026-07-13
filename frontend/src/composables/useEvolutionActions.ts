/**
 * Evolution fetch handlers + snapshot/drawer state — extracted from EvolutionDashboard.vue
 * (Phase 7 D round 8). Owns: drawerVisible, selectedSkillForDetail, snapshotIndex,
 * selectedSnapshotDate, and 3 fetch handlers + onSnapshotChange.
 */
import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { useEvolutionStore } from '@/stores/evolution'
import type { SnapshotEntry } from '@/stores/evolution'

type EvolutionStore = ReturnType<typeof useEvolutionStore>

export interface EvolutionActionsApi {
  drawerVisible: Ref<boolean>
  selectedSkillForDetail: Ref<string>
  snapshotIndex: Ref<number>
  selectedSnapshotDate: Ref<string>
  fetchTrends: () => Promise<void>
  fetchSnapshots: () => Promise<void>
  fetchChangelog: (skillName: string) => Promise<void>
  onSnapshotChange: (idx: number | number[]) => void
}

export function useEvolutionActions(store: EvolutionStore): EvolutionActionsApi {
  const drawerVisible: Ref<boolean> = ref(false)
  const selectedSkillForDetail: Ref<string> = ref('')
  const snapshotIndex: Ref<number> = ref(0)
  const selectedSnapshotDate: Ref<string> = ref('')

  async function fetchTrends(): Promise<void> {
    try {
      await store.fetchTrends()
    } catch (e) {
      // ponytail: error logging before user-facing message
      if (import.meta.env.DEV) console.error('[Evolution] Failed to fetch trends:', e)
      ElMessage.error('演化趋势数据加载失败')
    }
  }

  async function fetchSnapshots(): Promise<void> {
    try {
      await store.fetchSnapshots()
      const last = store.snapshots.length - 1
      if (last >= 0) {
        snapshotIndex.value = last
        const lastSnap: SnapshotEntry | undefined = store.snapshots[last]
        if (lastSnap) selectedSnapshotDate.value = lastSnap.snapshot_date
      }
    } catch (e) {
      if (import.meta.env.DEV) console.error('[Evolution] Failed to fetch snapshots:', e)
    }
  }

  function onSnapshotChange(idx: number | number[]): void {
    const i = Array.isArray(idx) ? idx[0] : idx
    const snap: SnapshotEntry | undefined = store.snapshots[i ?? 0]
    if (!snap) return
    selectedSnapshotDate.value = snap.snapshot_date
    ElMessage.info(`已切换到快照 ${snap.snapshot_date}（${snap.position_name}）`)
  }

  async function fetchChangelog(identifier: string): Promise<void> {
    selectedSkillForDetail.value = identifier
    drawerVisible.value = true
    try {
      await store.fetchChangelog(identifier)
    } catch (e) {
      if (import.meta.env.DEV) console.error('[Evolution] Failed to fetch changelog:', e)
    }
  }

  return {
    drawerVisible,
    selectedSkillForDetail,
    snapshotIndex,
    selectedSnapshotDate,
    fetchTrends,
    fetchSnapshots,
    fetchChangelog,
    onSnapshotChange,
  }
}
