/** Evolution panel: show/hide toggle + focus-position fetch + drawer state. */
import { ref, computed } from 'vue'
import { useGraphStore } from '@/stores/graph'

export function useEvolutionPanel() {
  const graphStore = useGraphStore()
  const showEvolution = ref(false)

  const graph3DEvolutionLinks = computed(() => {
    if (!showEvolution.value || graphStore.currentLayer !== 'position') return []
    const sourceName = graphStore.expandedKAName
    const posNodes = graphStore.positionsByKA.get(graphStore.expandedKAId ?? '') ?? []
    const positionNames = new Set(posNodes.map(p => p.properties.name))
    return graphStore.evolutionPaths
      .filter(e => {
        // D-04: keep edges whose source or target is a Position in the current domain
        const src = String(e.source_id)
        const tgt = String(e.target_id)
        return positionNames.has(src) || positionNames.has(tgt) ||
               src === sourceName || tgt === sourceName
      })
      .map(e => ({
        source: e.source_id,
        target: e.target_id,
        type: 'EVOLVES_TO' as const,
        properties: e.properties,
      }))
  })

  return {
    showEvolution,
    graph3DEvolutionLinks,
  }
}
