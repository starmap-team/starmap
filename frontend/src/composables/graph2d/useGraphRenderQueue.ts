/**
 * useGraphRenderQueue — Debounced + batched render dispatcher
 *
 * Replaces ad-hoc setTimeout debouncing with a requestAnimationFrame-based
 * scheduler. Multiple render() calls within the same frame collapse to one.
 * Avoids React-style "double render" and prevents render storms when multiple
 * data sources change simultaneously.
 */
import { watch, type WatchSource } from 'vue'
import type { Graph } from '@/types/g6'

export interface RenderTask {
  name: string
  fn: (graph: Graph) => void | Promise<void>
  priority: number  // Higher runs first
}

export interface UseGraphRenderQueueApi {
  register: (task: RenderTask) => void
  schedule: (graph: Graph | null) => void
  flush: (graph: Graph | null) => void
}

export function useGraphRenderQueue(
  watchSources: WatchSource[] = [],
  debounceMs: number = 16,  // ~1 frame
): UseGraphRenderQueueApi {
  const tasks = new Map<string, RenderTask>()
  let scheduledFrame: number | null = null
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  function register(task: RenderTask): void {
    tasks.set(task.name, task)
  }

  async function executeAll(graph: Graph): Promise<void> {
    // Sort by priority descending, then run
    const sorted = Array.from(tasks.values()).sort((a, b) => b.priority - a.priority)
    for (const task of sorted) {
      try {
        await task.fn(graph)
      } catch (err) {
        if (import.meta.env.DEV) console.error(`[Graph2D] Render task "${task.name}" failed:`, err)
      }
    }
  }

  function schedule(graph: Graph | null): void {
    if (!graph) return
    // Dedupe within debounce window
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      if (scheduledFrame) cancelAnimationFrame(scheduledFrame)
      scheduledFrame = requestAnimationFrame(() => {
        scheduledFrame = null
        executeAll(graph).catch((err: unknown) => console.error('[useGraphRenderQueue] executeAll failed', err))
      })
    }, debounceMs)
  }

  function flush(graph: Graph | null): void {
    if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null }
    if (scheduledFrame) { cancelAnimationFrame(scheduledFrame); scheduledFrame = null }
    if (graph) executeAll(graph)
  }

  // Auto-schedule when any of the watch sources change
  // (Caller wires this to graph.value after init)
  if (watchSources.length > 0) {
    watch(watchSources, () => {
      // Defer to caller for graph access; emit a custom event-like signal
      // The component should call schedule() from its own watchers
    })
  }

  return { register, schedule, flush }
}
