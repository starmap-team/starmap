/**
 * useGraph3DLOD — Level-of-Detail adapter for 3D graphs (mirror of useGraphLOD)
 *
 * Hides labels and simplifies node styles when node count exceeds threshold.
 * 2026-08-13: ( 全景图谱) Plan 01-03 Task 1 — 镜像 useGraphLOD.ts
 * 模式,为 Graph3D 提供 3D 渲染下的 LOD 阈值判断,节省 GPU 开销。
 */
import { ref, watch, type Ref } from 'vue'

export interface LODConfig3D {
  hideLabelsAbove: number  // Node count threshold above which labels hide
  simplifyAbove: number     // Node count threshold for simplified style
  defaultLabelsVisible: boolean
}

export interface UseGraph3DLODApi {
  shouldShowLabels: Readonly<Ref<boolean>>
  shouldSimplify: Readonly<Ref<boolean>>
  setNodeCount: (n: number) => void
}

export function useGraph3DLOD(config: LODConfig3D = { hideLabelsAbove: 30, simplifyAbove: 100, defaultLabelsVisible: true }): UseGraph3DLODApi {
  const nodeCount = ref(0)
  const shouldShowLabels = ref(config.defaultLabelsVisible)
  const shouldSimplify = ref(false)

  watch(nodeCount, (n) => {
    shouldShowLabels.value = n <= config.hideLabelsAbove
    shouldSimplify.value = n > config.simplifyAbove
  })

  return {
    shouldShowLabels,
    shouldSimplify,
    setNodeCount: (n: number) => { nodeCount.value = n },
  }
}