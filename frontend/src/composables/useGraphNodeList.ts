/**
 * Admin.vue graph node list state + filters — extracted from Admin.vue (Phase 7 D)
 * Pure composable: search keyword, type filter, status filter, pagination.
 */
import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'

export interface GraphNodeItem {
  id: string
  // P1-6 fix (functional-review 2026-08-13): Neo4j elementId，写操作首选标识
  // （服务端已改为 elementId OR canonical_id 双匹配，两者皆可）
  element_id?: string
  type: string
  name: string
  properties: Record<string, unknown>
  status: 'pending' | 'approved' | 'rejected'
  created_at?: string
}

export interface GraphNodeListApi {
  nodes: ComputedRef<GraphNodeItem[]>
  searchKeyword: Ref<string>
  typeFilter: Ref<string>
  statusFilter: Ref<string>          // E4 fix: was missing
  currentPage: Ref<number>
  pageSize: Ref<number>
  filtered: ComputedRef<GraphNodeItem[]>
  paged: ComputedRef<GraphNodeItem[]>
  resetPage: () => void
}

export function useGraphNodeList(source: ComputedRef<GraphNodeItem[]>): GraphNodeListApi {
  const nodes: ComputedRef<GraphNodeItem[]> = source
  const searchKeyword: Ref<string> = ref('')
  const typeFilter: Ref<string> = ref('')
  const statusFilter: Ref<string> = ref('')  // E4 fix: status dropdown
  const currentPage: Ref<number> = ref(1)
  const pageSize: Ref<number> = ref(10)

  const filtered: ComputedRef<GraphNodeItem[]> = computed(() => {
    let list = nodes.value
    if (searchKeyword.value) {
      const kw = searchKeyword.value.toLowerCase()
      list = list.filter(n => n.name.toLowerCase().includes(kw))
    }
    if (typeFilter.value) {
      list = list.filter(n => n.type === typeFilter.value)
    }
    if (statusFilter.value) {
      list = list.filter(n => n.status === statusFilter.value)
    }
    return list
  })

  const paged: ComputedRef<GraphNodeItem[]> = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    return filtered.value.slice(start, start + pageSize.value)
  })

  // Reset to page 1 when any filter changes (otherwise user lands on an
  // empty page after narrowing the filter set).
  watch([searchKeyword, typeFilter, statusFilter], () => {
    currentPage.value = 1
  })

  function resetPage(): void {
    currentPage.value = 1
  }

  return {
    nodes, searchKeyword, typeFilter, statusFilter,
    currentPage, pageSize, filtered, paged, resetPage,
  }
}
