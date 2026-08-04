/**
 * useG6Lifecycle — G6 instance lifecycle management
 *
 * Encapsulates: dynamic G6 import (with module-level cache), instance creation,
 * resize handling, and teardown. Exposes the live G6 instance as a shallowRef
 * to avoid Vue's deep reactivity overhead on G6's internal graph objects.
 */
import { onMounted, onUnmounted, ref, shallowRef, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { Graph, G6GraphClass } from '@/types/g6'
import { cv, g6TooltipStyle } from '@/utils/chartTheme'

export interface G6Options {
  width: number
  height: number
  layout?: Record<string, unknown>
  behaviors?: unknown[]
  plugins?: unknown[]
}

export interface UseG6LifecycleApi {
  graph: Readonly<Ref<Graph | null>>
  containerRef: Ref<HTMLElement | null>
  init: (opts: G6Options) => Promise<void>
  destroy: () => void
}

let _G6GraphClass: G6GraphClass | null = null
async function loadG6Graph(): Promise<G6GraphClass> {
  if (!_G6GraphClass) {
    const g6 = await import('@antv/g6')
    _G6GraphClass = g6.Graph
  }
  return _G6GraphClass
}

export function useG6Lifecycle(): UseG6LifecycleApi {
  const graph = shallowRef<Graph | null>(null)
  const containerRef = ref<HTMLElement | null>(null)

  function handleResize() {
    if (!graph.value || !containerRef.value) return
    graph.value.setSize(containerRef.value.clientWidth, containerRef.value.clientHeight)
  }

  async function init(opts: G6Options): Promise<void> {
    if (!containerRef.value) return
    if (graph.value) { graph.value.destroy(); graph.value = null }
    try {
      const GraphClass = await loadG6Graph()
      graph.value = new GraphClass({
        container: containerRef.value,
        width: opts.width,
        height: opts.height,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        layout: (opts.layout ?? { type: 'force', preventOverlap: true, nodeSize: 40, nodeSpacing: 20, animate: false }) as any,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        // G6 v5 label config must be nested under `label`
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        node: { style: { label: { placement: 'bottom' as const, offsetY: 8, fill: cv('--foreground'), fontSize: 12, fontFamily: "'PingFang SC', 'Microsoft YaHei', sans-serif" } } } as any,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        edge: { style: { stroke: cv('--border'), lineWidth: 1.5, opacity: 0.5, endArrow: true } } as any,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        behaviors: (opts.behaviors ?? ['drag-canvas', 'zoom-canvas', 'drag-element', { type: 'hover-activate', degree: 1, direction: 'both' }]) as any,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        plugins: (opts.plugins ?? [
          { type: 'minimap', size: [140, 90], position: 'bottom-right', padding: 8 },
          { type: 'tooltip', enable: true, trigger: 'pointerenter', offset: [10, 10], style: { ...g6TooltipStyle(), borderRadius: '12px', boxShadow: '0 8px 24px rgba(0,0,0,0.12)', padding: '10px 14px' } },
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ]) as any,
      })
    } catch (err) {
      if (import.meta.env.DEV) console.error('[Graph2D] Failed to initialize graph:', err)
      ElMessage.error('图谱加载失败，请确认后端服务已启动')
    }
  }

  function destroy(): void {
    if (graph.value) { graph.value.destroy(); graph.value = null }
  }

  onMounted(() => window.addEventListener('resize', handleResize))
  onUnmounted(() => { window.removeEventListener('resize', handleResize); destroy() })

  return { graph, containerRef, init, destroy }
}
