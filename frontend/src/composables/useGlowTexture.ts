/**
 * useGlowTexture — Canvas-based radial gradient glow texture generator with caching.
 *
 * Extracted from Graph3D.vue to decouple the glow rendering pipeline
 * from the component lifecycle.
 */
import type * as THREE from 'three'

// ── Glow texture cache (key = hexColor) ──
const _glowCache = new Map<number, THREE.Texture>()

/**
 * Create a radial-gradient glow texture on an off-screen canvas.
 * Results are cached by hex colour key — same colour reuses the same texture.
 */
export function createGlowTexture(hexColor: number, THREE_NS: typeof import('three')): THREE.Texture {
  const cached = _glowCache.get(hexColor)
  if (cached) return cached

  const size = 128
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!

  // Extract RGB from hex
  const r = (hexColor >> 16) & 0xff
  const g = (hexColor >> 8) & 0xff
  const b = hexColor & 0xff

  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.6)`)
  gradient.addColorStop(0.3, `rgba(${r}, ${g}, ${b}, 0.25)`)
  gradient.addColorStop(0.7, `rgba(${r}, ${g}, ${b}, 0.08)`)
  gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`)
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, size, size)

  const texture = new THREE_NS.CanvasTexture(canvas)
  texture.needsUpdate = true
  _glowCache.set(hexColor, texture)
  return texture
}

/** Dispose all cached glow textures (call on component unmount). */
export function disposeGlowCache() {
  for (const texture of _glowCache.values()) texture.dispose()
  _glowCache.clear()
}
