/**
 * useGraph3DLifecycle — 3d-force-graph instance lifecycle composable
 *
 * 2026-08-13: (M1 全景图谱) Plan 01-04 Task 1 — Graph3D.vue 单体拆分 (C-3)
 *
 * 沿 loop_orchestrator.py 987→199 兼容壳先例: composable **代理调用**
 * 既有方法体,保 monkeypatch 兼容。本 composable 不重复实现 initGraph / destroyGraph,
 * 仅暴露 useGraph3DLifecycle hook 让 Graph3D.vue 调用方获得统一 lifecycle 接口
 * (instance / isInitializing / lastNamespace refs + 命名空间检测 + destructor 助手)。
 *
 * 既有 initGraph 等方法保留在 Graph3D.vue 内 (兼容既有测试 + monkeypatch)。
 */
import { ref, type Ref } from 'vue'

export interface Graph3DLifecycle {
  /** ForceGraph3D instance (shallowRef per Graph3D.vue:50) */
  instance: Ref<unknown>
  /** 是否正在初始化 */
  isInitializing: Ref<boolean>
  /** 上次 namespace (ts-/ka-/lv-/heat prefix),用于维度切换时重建检测 */
  lastNamespace: Ref<string | null>
  /** 检测节点 id 前缀以判断 namespace */
  detectNamespace: (modeOrId: string) => string
  /** 销毁 ForceGraph3D 实例 (清空 lastNamespace) */
  destructor: () => void
}

export function useGraph3DLifecycle(): Graph3DLifecycle {
  const instance = ref<unknown>(null)
  const isInitializing = ref(false)
  const lastNamespace = ref<string | null>(null)

  function detectNamespace(modeOrId: string): string {
    if (modeOrId.startsWith('ts-')) return 'tech_stack'
    if (modeOrId.startsWith('ka-') || modeOrId.startsWith('ind-')) return 'domain'
    if (modeOrId.startsWith('lv-')) return 'level'
    if (modeOrId.startsWith('heat-')) return 'heat'
    return 'unknown'
  }

  function destructor(): void {
    instance.value = null
    isInitializing.value = false
    lastNamespace.value = null
  }

  return { instance, isInitializing, lastNamespace, detectNamespace, destructor }
}