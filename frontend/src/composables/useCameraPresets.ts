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

  /** 根据节点实际空间分布计算 bounding box，返回相机所需最小距离 */
  function calcFitDistance(padding = 1.3): number {
    const ns = nodes()
    if (ns.length === 0) return 400

    // 从已有节点位置中提取 bounding box
    let minX = Infinity, maxX = -Infinity
    let minY = Infinity, maxY = -Infinity
    let minZ = Infinity, maxZ = -Infinity
    for (const n of ns) {
      if (n.x !== undefined) { minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x) }
      if (n.y !== undefined) { minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y) }
      if (n.z !== undefined) { minZ = Math.min(minZ, n.z); maxZ = Math.max(maxZ, n.z) }
    }
    // 防御：节点全无坐标时回退到 nodeCount 启发式
    if (minX === Infinity) return Math.max(400, ns.length * 3)

    const extentX = (maxX - minX) / 2
    const extentY = (maxY - minY) / 2
    const extentZ = (maxZ - minZ) / 2
    // 取最大半轴作为球体半径，乘 padding 确保边缘节点可见
    const radius = Math.max(extentX, extentY, extentZ, 50)
    return radius * padding
  }

  function setCameraPreset(preset: CameraPreset) {
    const graph = graphInstance.value
    if (!graph) return

    // Stop auto-rotate during transition
    const controls = graph.controls()
    if (controls) {
      controls.autoRotate = false
    }

    const dist = { x: 0, y: 0, z: 0 }
    const fitDist = calcFitDistance()

    switch (preset) {
      case 'overview':
        // 全景：基于 bounding box 距离 + 角度偏移
        dist.x = fitDist * 0.7
        dist.y = fitDist * 0.5
        dist.z = fitDist * 0.9
        break

      case 'domain':
        // 中距：domain 聚类视角
        dist.x = fitDist * 0.5
        dist.y = fitDist * 0.7
        dist.z = fitDist * 0.6
        break

      case 'position':
        // 近距：position-skill 网络
        dist.x = fitDist * 0.4
        dist.y = fitDist * 0.4
        dist.z = fitDist * 0.9
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

  /** Reset camera to initial position — 同样基于 bounding box */
  function resetCamera() {
    const graph = graphInstance.value
    if (!graph) return
    const fitDist = calcFitDistance(1.5)
    graph.cameraPosition(
      { x: fitDist * 0.6, y: fitDist * 0.5, z: fitDist * 0.8 },
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
    calcFitDistance,
  }
}
