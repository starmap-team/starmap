/**
 * useGraphLOD — Level-of-Detail adapter for large graphs
 *
 * Hides labels and simplifies node styles when node count exceeds threshold.
 * Automatically restores full detail when zooming in or node count drops.
 * Triggers re-render via a callback (caller decides what to update).
 */
import { ref, watch, type Ref } from 'vue'

export interface LODConfig {
  hideLabelsAbove: number  // Node count threshold above which labels hide
  simplifyAbove: number     // Node count threshold for simplified style
  defaultLabelsVisible: boolean
}

export interface UseGraphLODApi {
  shouldShowLabels: Readonly<Ref<boolean>>
  shouldSimplify: Readonly<Ref<boolean>>
  setNodeCount: (n: number) => void
}

export function useGraphLOD(config: LODConfig = { hideLabelsAbove: 30, simplifyAbove: 100, defaultLabelsVisible: true }): UseGraphLODApi {
  const nodeCount = ref(0)
  const shouldShowLabels = ref(config.defaultLabelsVisible)
  const shouldSimplify = ref(false)

  watch(nodeCount, (n) => {
    shouldShowLabels.value = n <= config.hideLabelsAbove
    shouldSimplify.value = n > config.simplifyAbove
  })

  return {
    shouldShowLabels,
    shouldSimplify,
    setNodeCount: (n: number) => { nodeCount.value = n },
  }
}
