/**
 * useZoomControls — Zoom and fit-view logic for 3D force graph.
 *
 * Handles zoomBy, zoomIn, zoomOut, and fitView by adjusting camera
 * distance relative to the lookAt center (always 0,0,0).
 * Extracted from Graph3D.vue to decouple zoom control from the component.
 */
import type { ShallowRef } from 'vue'

export function useZoomControls(
  graphInstance: ShallowRef<any>, // eslint-disable-line @typescript-eslint/no-explicit-any
  calcFitDistance: (padding?: number) => number,
) {
  /** Zoom camera by a multiplicative factor relative to center */
  function zoomBy(factor: number) {
    const graph = graphInstance.value
    if (!graph) return
    const cam = graph.cameraPosition()
    if (!cam) return
    // cam = { x, y, z } — current camera position; lookAt is always (0,0,0)
    graph.cameraPosition(
      { x: cam.x * factor, y: cam.y * factor, z: cam.z * factor },
      { x: 0, y: 0, z: 0 },
      400,
    )
  }

  function zoomIn() { zoomBy(0.8) }   // move camera closer
  function zoomOut() { zoomBy(1.25) }  // move camera farther

  /** Fit all nodes into view — same logic as resetCamera but with tighter padding */
  function fitView() {
    const graph = graphInstance.value
    if (!graph) return
    const fitDist = calcFitDistance(1.3)
    graph.cameraPosition(
      { x: fitDist * 0.6, y: fitDist * 0.5, z: fitDist * 0.8 },
      { x: 0, y: 0, z: 0 },
      800,
    )
  }

  return { zoomBy, zoomIn, zoomOut, fitView }
}
