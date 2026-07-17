/**
 * useNodeTooltip — Tooltip state and handlers for 3D graph nodes.
 *
 * Manages tooltip position, visibility, and node data.
 * Provides onNodeHover handler and mousemove listener setup/teardown.
 * Extracted from Graph3D.vue to decouple tooltip logic from the component.
 */
import { ref } from 'vue'
import { type GraphNode3D, getNodeLabel } from './useNodeThreeObject'

export interface TooltipNode {
  id: string; name: string; type: string;
  position_count?: number; skill_count?: number;
  proficiency?: string; category?: string
}

export function useNodeTooltip() {
  const tooltipNode = ref<TooltipNode | null>(null)
  const tooltipX = ref(0)
  const tooltipY = ref(0)
  const tooltipVisible = ref(false)

  let _mouseMoveHandler: ((e: MouseEvent) => void) | null = null

  /** Create onNodeHover handler for 3d-force-graph */
  function createHoverHandler(
    onHover?: (node: GraphNode3D | null) => void,
  ) {
    let _prevHoveredNode: GraphNode3D | null = null

    function _setTextSpriteVisible(nodeObj: GraphNode3D, visible: boolean) {
      const threeObj = (nodeObj as unknown as { __threeObj?: import('three').Object3D }).__threeObj
      if (!threeObj) return
      threeObj.traverse((child) => {
        if (child.type === 'Sprite' && child.userData.isTextSprite) {
          child.visible = visible
        }
      })
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (node: any) => {
      const typed = node as GraphNode3D | null
      // Restore previous node's textSprite
      if (_prevHoveredNode) {
        _setTextSpriteVisible(_prevHoveredNode, true)
        _prevHoveredNode = null
      }
      if (typed) {
        _setTextSpriteVisible(typed, false)
        _prevHoveredNode = typed
        tooltipNode.value = {
          id: String(typed.id), name: typed.properties.name, type: getNodeLabel(typed),
          position_count: typed.properties.position_count, skill_count: typed.properties.skill_count,
          proficiency: typed.properties.proficiency, category: typed.properties.category,
        }
        tooltipVisible.value = true
      } else {
        tooltipVisible.value = false
        tooltipNode.value = null
      }
      onHover?.(typed)
    }
  }

  /** Attach mousemove listener to container for tooltip positioning */
  function attachMouseMoveListener(container: HTMLElement) {
    _mouseMoveHandler = (e: MouseEvent) => { tooltipX.value = e.clientX; tooltipY.value = e.clientY }
    container.addEventListener('mousemove', _mouseMoveHandler)
  }

  /** Remove mousemove listener from container (call on unmount) */
  function detachMouseMoveListener(container: HTMLElement) {
    if (_mouseMoveHandler) {
      container.removeEventListener('mousemove', _mouseMoveHandler)
      _mouseMoveHandler = null
    }
  }

  return {
    tooltipNode,
    tooltipX,
    tooltipY,
    tooltipVisible,
    createHoverHandler,
    attachMouseMoveListener,
    detachMouseMoveListener,
  }
}
