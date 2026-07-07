/** KA → color map (used by both 2D and 3D rendering paths). */
import { computed } from 'vue'
import { useGraphStore } from '@/stores/graph'
import { KA_FALLBACK_COLORS } from '@/utils/graphColors'

export function useGraph2DData() {
  const graphStore = useGraphStore()

  const kaColorMap = computed(() => {
    const map = new Map<string, string>()
    graphStore.domains.forEach((d, i) => {
      map.set(d.id, d.color || KA_FALLBACK_COLORS[i % KA_FALLBACK_COLORS.length])
    })
    return map
  })

  return {
    kaColorMap,
  }
}
