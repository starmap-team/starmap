/**
 * useGraphAnimation — Node entrance growth animation (G6 v5 compatible)
 *
 * Animates nodes from small scale (scale:0.1) → full size (scale:1).
 * Assumes the caller (layer renderer) has already set initial small scale
 * via setData/updateNodeData before calling animate().
 *
 * Uses setTimeout-based staggered reveal with graph.draw() after each update.
 * Cancels any in-flight animation before starting a new one.
 */
import { shallowRef } from 'vue'
import type { Graph } from '@/types/g6'

export interface UseGraphAnimationApi {
  cancel: () => void
  animate: (graph: Graph | null, nodeIds: string[], intervalMs?: number) => Promise<void>
}

export function useGraphAnimation(defaultIntervalMs: number = 220): UseGraphAnimationApi {
  const timer = shallowRef<ReturnType<typeof setTimeout> | null>(null)

  function cancel(): void {
    if (timer.value) {
      clearTimeout(timer.value)
      timer.value = null
    }
  }

  async function animate(graph: Graph | null, nodeIds: string[], intervalMs: number = defaultIntervalMs): Promise<void> {
    cancel()
    if (!nodeIds.length || !graph) return

    return new Promise<void>((resolve) => {
      let index = 0

      const revealNext = (): void => {
        if (index >= nodeIds.length || !graph) { resolve(); return }

        const nodeId = nodeIds[index]
        if (!nodeId) { resolve(); return }

        try {
          // Phase 1: overshoot for elastic feel
          graph.updateNodeData([{
            id: nodeId,
            style: {
              scale: 1.2,
              opacity: 1,
              fillOpacity: 0.9,
            },
          }])
          graph.draw()

          // Phase 2: settle to normal size
          timer.value = setTimeout(() => {
            if (!graph) return
            graph.updateNodeData([{
              id: nodeId,
              style: {
                scale: 1,
              },
            }])
            graph.draw()
          }, 250)
        } catch (e) {
          console.warn('[useGraphAnimation] Failed to animate node:', nodeId, e)
        }

        index += 1
        if (index < nodeIds.length) {
          timer.value = setTimeout(revealNext, intervalMs)
        } else {
          timer.value = null
          resolve()
        }
      }

      timer.value = setTimeout(revealNext, intervalMs)
    })
  }

  return { cancel, animate }
}