/** KPI 指标计算 composable — 从 Home.vue 提取。 */
import { computed } from 'vue'
import { useGraphStore } from '@/stores/graph'

/** 计算全景图谱的 KPI 指标。
 * 
 * 注意：岗位数和技能数使用后端 /graph/overview 返回的独立节点计数
 * (independent_positions / independent_skills)，而非 domains 数组的累加值。
 * 这样可以避免同一个 Position/Skill 被多个 KnowledgeArea 重复计数，
 * 确保前端显示与 Neo4j 实际节点数一致。
 */
export function useKPIMetrics() {
  const graphStore = useGraphStore()

  // 岗位数：使用后端返回的独立节点数（去重，与 Neo4j 实际一致）
  const totalPositions = computed(() =>
    graphStore.independentPositions ??
    graphStore.domains.reduce((s, d) => s + d.position_count, 0),
  )

  // 技能数：使用后端返回的独立节点数（去重，与 Neo4j 实际一致）
  const totalSkills = computed(() =>
    graphStore.independentSkills ??
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
