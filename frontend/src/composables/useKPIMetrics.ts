/** KPI 指标计算 composable — 从 Home.vue 提取。 */
import { computed } from 'vue'
import { useGraphStore } from '@/stores/graph'

/** 计算全景图谱的 KPI 指标。 */
export function useKPIMetrics() {
  const graphStore = useGraphStore()

  const totalPositions = computed(() =>
    graphStore.domains.reduce((s, d) => s + d.position_count, 0),
  )

  const totalSkills = computed(() =>
    graphStore.domains.reduce((s, d) => s + d.skill_count, 0),
  )

  const totalDomains = computed(() => graphStore.domains.length)

  const totalRelations = computed(() => {
    // domain 层用 domainConnections，更深层用 allEdges
    if (graphStore.currentLayer === 'domain') {
      return graphStore.domainConnections?.length ?? 0
    }
    return graphStore.allEdges?.length ?? 0
  })

  const totalNodes = computed(() =>
    totalPositions.value + totalSkills.value + totalDomains.value,
  )

  return {
    totalPositions,
    totalSkills,
    totalDomains,
    totalRelations,
    totalNodes,
  }
}
