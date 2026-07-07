/** Home page view mode (2D/3D) + 3D auto-rotate toggle. */
import { ref } from 'vue'

export type ViewMode = '2d' | '3d'

export function useHomeLayout() {
  const viewMode = ref<ViewMode>('3d')
  const autoRotate3D = ref(false)

  return {
    viewMode,
    autoRotate3D,
  }
}
