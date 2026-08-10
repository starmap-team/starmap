/** Graph toolbar state — layout/maxNodes/proficiency filters, plain refs. */
import { ref } from 'vue'
import { PROFICIENCY_LEVELS } from '@/constants/labels'

export type LayoutMode = 'force' | 'dagre' | 'radial'

const DEFAULT_PROFICIENCY = PROFICIENCY_LEVELS

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
