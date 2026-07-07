/** Graph toolbar state — layout/maxNodes/proficiency filters, plain refs. */
import { ref } from 'vue'

export type LayoutMode = 'force' | 'dagre' | 'radial'

const DEFAULT_PROFICIENCY = ['精通', '熟悉', '了解'] as const

export function useGraphToolbarState() {
  const layoutMode = ref<LayoutMode>('force')
  const maxNodesLimit = ref(80)
  const proficiencyFilter = ref<string[]>([...DEFAULT_PROFICIENCY])

  function toggleLayout() {
    layoutMode.value =
      layoutMode.value === 'force' ? 'dagre'
        : layoutMode.value === 'dagre' ? 'radial' : 'force'
  }

  function onMaxNodesChange(val: number) {
    maxNodesLimit.value = val
  }
  function onProficiencyFilter(levels: string[]) {
    proficiencyFilter.value = levels
  }

  return {
    layoutMode,
    maxNodesLimit,
    proficiencyFilter,
    toggleLayout,
    onMaxNodesChange,
    onProficiencyFilter,
  }
}
