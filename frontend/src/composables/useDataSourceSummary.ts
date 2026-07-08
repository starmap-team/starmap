/**
 * DataSources summary statistics — extracted from DataSources.vue (Phase 7 D round 13).
 * Pure computed over the data source store; no timers, no side effects.
 */
import { computed, type ComputedRef } from 'vue'
import type { useDataSourceStore } from '@/stores/datasource'

type DataSourceStore = ReturnType<typeof useDataSourceStore>

export interface DataSourceSummary {
  total: number
  active: number
  totalRecords: number
  avgQuality: number
}

export function useDataSourceSummary(
  store: DataSourceStore,
): ComputedRef<DataSourceSummary> {
  return computed(() => {
    const src = store.sources
    return {
      total: src.length,
      active: src.filter(s => s.status === 'active').length,
      totalRecords: src.reduce((sum, s) => sum + s.total_records, 0),
      avgQuality: src.length
        ? src.reduce((sum, s) => sum + s.avg_quality_score, 0) / src.length
        : 0,
    }
  })
}
