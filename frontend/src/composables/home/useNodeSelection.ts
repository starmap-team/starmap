/** Selected node state + 2D/3D node-click bridge. */
import { ref } from 'vue'
import { useGraphStore, type GraphNode } from '@/stores/graph'

export function useNodeSelection() {
  const graphStore = useGraphStore()
  const selectedNode = ref<GraphNode | null>(null)

  function clearSelection() {
    selectedNode.value = null
  }

  return {
    selectedNode,
    clearSelection,
    graphStore,
  }
}
