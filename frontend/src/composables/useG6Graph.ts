import { onMounted, onBeforeUnmount, type Ref } from 'vue'
import { ensureG6Loaded } from './useG6'
import type { Graph, GraphOptions } from '@/types/g6'

/**
 * Shared G6 graph lifecycle: create, resize, destroy.
 * ponytail: replaces duplicated mount/resize/destroy in CareerPathGraph & LearningPathFlow.
 */
export function useG6Graph(containerRef: Ref<HTMLElement | null>) {
  let graph: Graph | null = null

  async function createGraph(options: GraphOptions) {
    if (!containerRef.value) return
    if (graph) { graph.destroy(); graph = null }

    const container = containerRef.value
    const width = container.clientWidth || 700
    const height = container.clientHeight || 300

    const GraphClass = await ensureG6Loaded()
    graph = new GraphClass({ container, width, height, ...options })
    return graph
  }

  function handleResize() {
    if (graph && containerRef.value) {
      graph.setSize(containerRef.value.clientWidth, containerRef.value.clientHeight)
    }
  }

  function destroyGraph() {
    window.removeEventListener('resize', handleResize)
    if (graph) { graph.destroy(); graph = null }
  }

  function mountGraph() {
    window.addEventListener('resize', handleResize)
  }

  onMounted(mountGraph)
  onBeforeUnmount(destroyGraph)

  return { graph, createGraph, handleResize, destroyGraph, mountGraph }
}
