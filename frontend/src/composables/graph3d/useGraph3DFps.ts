/**
 * useGraph3DFps — 3D 渲染 FPS 监控 composable
 *
 * 2026-08-13: Phase 1 (M1 全景图谱) Plan 01-04 Task 2 — 抽 Graph3D.vue:324-331
 * FPS 监控逻辑(原 line 46 fps ref + line 302+ fpsFrames/fpsLastTime/fpsRafId)。
 *
 * 与 Graph3D.vue 既有实现保持一致 (rafId-based loop,每秒计算 fps,onUnmounted 取消)。
 * 暴露 fps (ReadonlyRef) + set(value) + start/stop,让外部 (Graph3D.vue 既有
 * measureFPS loop) 可以更新 fps 而无需持有 ref setter。
 */
import { ref, onUnmounted, type Ref } from 'vue'

export interface Graph3DFps {
  fps: Readonly<Ref<number>>
  set: (value: number) => void
  start: () => void
  stop: () => void
}

export function useGraph3DFps(): Graph3DFps {
  const fps = ref(0)
  let frames = 0
  let lastTime = performance.now()
  let rafId = 0

  function tick() {
    frames++
    const now = performance.now()
    if (now - lastTime >= 1000) {
      fps.value = frames
      frames = 0
      lastTime = now
    }
    rafId = requestAnimationFrame(tick)
  }

  function start() {
    stop()
    rafId = requestAnimationFrame(tick)
  }

  function stop() {
    if (rafId) cancelAnimationFrame(rafId)
    rafId = 0
  }

  function set(value: number) {
    fps.value = value
  }

  onUnmounted(stop)

  return { fps, set, start, stop }
}