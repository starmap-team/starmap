/**
 * Admin.vue graph node list state + filters — extracted from Admin.vue (Phase 7 D)
 * Pure composable: search keyword, type filter, pagination over a list of nodes.
 */
import { computed, ref, type ComputedRef, type Ref } from 'vue'

export interface GraphNodeItem {
  id: string
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
    return list
  })

  const paged: ComputedRef<GraphNodeItem[]> = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    return filtered.value.slice(start, start + pageSize.value)
  })

  function resetPage(): void {
    currentPage.value = 1
  }

  return { nodes, searchKeyword, typeFilter, currentPage, pageSize, filtered, paged, resetPage }
}
