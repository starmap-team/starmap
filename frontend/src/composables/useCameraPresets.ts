/**
 * useCameraPresets — Camera positioning logic for 3D force graph.
 *
 * Handles camera presets, reset, and auto-rotate toggle.
 * Extracted from Graph3D.vue to decouple camera control from the component.
 */
import { ref, type ShallowRef } from 'vue'
import type { GraphNode3D } from './useNodeThreeObject'

export type CameraPreset = 'overview' | 'domain' | 'position'

export function useCameraPresets(
  graphInstance: ShallowRef<any>, // eslint-disable-line @typescript-eslint/no-explicit-any
  nodes: () => GraphNode3D[],
) {
  const autoRotate = ref(false)
  let _autoRotateTimer: ReturnType<typeof setTimeout> | null = null

  function setCameraPreset(preset: CameraPreset) {
    const graph = graphInstance.value
    if (!graph) return

    // Stop auto-rotate during transition
    const controls = graph.controls()
    if (controls) {
      controls.autoRotate = false
    }

    const dist = { x: 0, y: 0, z: 0 }
    let distance = 0
    const nodeCount = nodes().length

    switch (preset) {
      case 'overview':
        // Pull camera far back for panoramic view
        distance = Math.max(400, nodeCount * 3.5)
        dist.x = distance * 0.7
        dist.y = distance * 0.5
        dist.z = distance * 0.9
        break

      case 'domain':
        // Closer, angled view focusing on domain clusters
        distance = Math.max(250, nodeCount * 1.8)
        dist.x = distance * 0.5
        dist.y = distance * 0.7
        dist.z = distance * 0.6
        break

      case 'position':
        // Tight view for position-skill networks
        distance = Math.max(180, nodeCount * 1.2)
        dist.x = distance * 0.4
        dist.y = distance * 0.4
        dist.z = distance * 0.9
        break
    }

    // Animate camera position
    graph.cameraPosition(
      { x: dist.x, y: dist.y, z: dist.z },
      { x: 0, y: 0, z: 0 },  // lookAt center
      1500  // transition duration ms
    )

    // Restore auto-rotate after transition
    if (autoRotate.value) {
      _autoRotateTimer = setTimeout(() => {
        if (controls) controls.autoRotate = true
      }, 1600)
    }
  }

  /** Reset camera to initial position */
  function resetCamera() {
    const graph = graphInstance.value
    if (!graph) return
    const dist = Math.max(350, nodes().length * 2.5)
    graph.cameraPosition(
      { x: dist * 0.6, y: dist * 0.5, z: dist * 0.8 },
      { x: 0, y: 0, z: 0 },
      1200
    )
  }

  /** Toggle auto-rotate on/off */
  function toggleAutoRotate() {
    autoRotate.value = !autoRotate.value
    const graph = graphInstance.value
    if (!graph) return
    const controls = graph.controls()
    if (controls) {
      controls.autoRotate = autoRotate.value
      controls.autoRotateSpeed = 0.8
    }
  }

  /** Clear the auto-rotate timer (call on unmount) */
  function clearAutoRotateTimer() {
    if (_autoRotateTimer) {
      clearTimeout(_autoRotateTimer)
      _autoRotateTimer = null
    }
  }

  return {
    autoRotate,
    setCameraPreset,
    resetCamera,
    toggleAutoRotate,
    clearAutoRotateTimer,
  }
}
