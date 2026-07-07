/** 3D graph data derivation (graph3DNodes / graph3DLinks) using precomputed KA colors. */
import { computed } from 'vue'
import { useGraphStore } from '@/stores/graph'
import { KA_FALLBACK_COLORS, nodeColor } from '@/utils/graphColors'
import { useGraph2DData } from './useGraph2DData'

export function useGraph3DData() {
  const graphStore = useGraphStore()
  const { kaColorMap } = useGraph2DData()

  const graph3DNodes = computed(() =>
    graphStore.visibleNodes.map(n => {
      const props = n.properties as Record<string, any>
      let color = nodeColor(n.labels[0])
      if (n.labels[0] === 'KnowledgeArea') {
        color = kaColorMap.value.get(n.id) ?? KA_FALLBACK_COLORS[0]
      }
      return {
        id: n.id,
        labels: n.labels,
        color,
        properties: {
          name: props.name,
          category: props.category,
          proficiency: props.proficiency,
          position_count: props.position_count,
          skill_count: props.skill_count,
          weight: props.weight,
        },
      }
    }),
  )

  const graph3DLinks = computed(() =>
    graphStore.visibleEdges.map(e => ({
      source: e.source_id,
      target: e.target_id,
      type: e.type,
      properties: e.properties,
    })),
  )

  return {
    graph3DNodes,
    graph3DLinks,
  }
}
