/**
 * DataSource sync trigger — extracted from DataSources.vue (Phase 7 D round 7).
 * Toast messages owned by ElMessage — kept inline for ops visibility.
 *
 * Note: source editor dialog (handleEditSource/Save) was originally defined but no
 * el-dialog exists in the page template — those handlers are dead code. They are
 * not extracted here; if the editor dialog is reintroduced, recompose from store.
 */
import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { useDataSourceStore } from '@/stores/datasource'
import type { DataSourceDetail } from '@/stores/datasource'

type DataSourceStore = ReturnType<typeof useDataSourceStore>

export interface DataSourceSyncApi {
  syncingIds: Ref<Set<string>>
  isSyncing: (id: string) => boolean
  handleSync: (source: DataSourceDetail) => Promise<void>
}

export function useDataSourceSync(store: DataSourceStore): DataSourceSyncApi {
  const syncingIds: Ref<Set<string>> = ref(new Set())

  function isSyncing(id: string): boolean {
    return syncingIds.value.has(id)
  }

  async function handleSync(source: DataSourceDetail): Promise<void> {
    if (syncingIds.value.has(source.id)) return
    syncingIds.value.add(source.id)
    try {
      const ok = await store.triggerSync(source.id)
      if (ok) {
        ElMessage.success(`${source.name} 同步已触发`)
      } else {
        ElMessage.error(`${source.name} 同步失败`)
      }
    } catch {
      ElMessage.error(`${source.name} 同步失败`)
    } finally {
      syncingIds.value.delete(source.id)
    }
  }

  return { syncingIds, isSyncing, handleSync }
}
