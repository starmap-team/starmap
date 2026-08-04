/**
 * Unified Graph3D composable — merges 6 single-caller composables:
 *   useForceConfig (167L) + useZoomControls (44L) + useNodeTooltip (90L)
 *   + useCameraPresets (144L) + useEvolutionEdges (74L) + useGlowTexture (49L)
 *
 * All 6 were served only by Graph3D.vue. Merging removes 5 files + 5 import chains
 * with zero logic change (ponytail: single-caller abstractions → co-locate).
 */
import { ref, type ShallowRef } from 'vue'
import type { LinkObject } from '3d-force-graph'
import type * as THREE from 'three'
import { chartColors } from '@/utils/chartTheme'
import { displayName, withAlpha } from '@/utils/graphColors'
import type { GraphNode3D } from './useNodeThreeObject'
import { getNodeLabel, proficiencyToZ } from './useNodeThreeObject'

// =============================================================================
// 1. ForceConfig — force engine tuning and collision configuration
// =============================================================================

export interface ForceConfig {
  chargeStrength: number
  linkDist: number
  linkStrength: number
  alphaDecay: number
  velocityDecay: number
  warmupTicks: number
  cooldownTicks: number
}

/** Calculate force configuration parameters based on node count and link density. */
export function calcForceConfig(nodeCount: number, linkCount?: number): ForceConfig {
  // Sparse graph (few links relative to nodes) — reduce charge strength
  // so unconnected nodes don't fly apart (heat view, bug #2)
  const sparse = linkCount !== undefined && linkCount < nodeCount * 0.3
  if (nodeCount <= 3) {
    if (sparse) return { chargeStrength: -200, linkDist: 200, linkStrength: 0.02, alphaDecay: 0.02, velocityDecay: 0.4, warmupTicks: 200, cooldownTicks: 600 }
    return { chargeStrength: -600, linkDist: 200, linkStrength: 0.02, alphaDecay: 0.02, velocityDecay: 0.4, warmupTicks: 200, cooldownTicks: 600 }
  }
  if (nodeCount <= 10) {
    if (sparse) return { chargeStrength: -100, linkDist: 160, linkStrength: 0.05, alphaDecay: 0.03, velocityDecay: 0.4, warmupTicks: 120, cooldownTicks: 400 }
    return { chargeStrength: -350, linkDist: 160, linkStrength: 0.05, alphaDecay: 0.03, velocityDecay: 0.4, warmupTicks: 120, cooldownTicks: 400 }
  }
  if (sparse) {
    return { chargeStrength: -80, linkDist: 120, linkStrength: 0.08, alphaDecay: 0.04, velocityDecay: 0.5, warmupTicks: 80, cooldownTicks: 300 }
  }
  return {
    chargeStrength: nodeCount > 200 ? -400 : -250,
    linkDist: nodeCount > 100 ? 180 : 120,
    linkStrength: nodeCount > 100 ? 0.03 : 0.08,
    alphaDecay: nodeCount > 300 ? 0.08 : 0.04,
    velocityDecay: nodeCount > 300 ? 0.5 : 0.35,
    warmupTicks: nodeCount > 300 ? 50 : 80,
    cooldownTicks: nodeCount > 300 ? 150 : 300,
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type GraphInstance = any

/** Apply force configuration to a 3d-force-graph instance. */
export function applyForceConfig(
  graph: GraphInstance, nodeCount: number, nodeCollisionPadding: number,
  getNodeRadius: (node: GraphNode3D) => number, isInit: boolean = true,
  linkCount?: number,
): void {
  const cfg = calcForceConfig(nodeCount, linkCount)

  const chargeForce = graph.d3Force('charge') as unknown as { strength(v: number): unknown; distanceMax(v: number): unknown } | null
  if (chargeForce) { chargeForce.strength(cfg.chargeStrength); chargeForce.distanceMax(isInit ? 1200 : 600) }

  const linkForce = graph.d3Force('link') as unknown as { distance(v: number): unknown; strength(v: number): unknown } | null
  if (linkForce) { linkForce.distance(cfg.linkDist); linkForce.strength(cfg.linkStrength) }

  const centerForce = graph.d3Force('center') as unknown as { strength(v: number): unknown } | null
  if (centerForce) centerForce.strength(isInit ? 0.008 : 0.02)

  const collisionForce = graph.d3Force('collision') as unknown as {
    strength(v: number): unknown; radius(v: (node: unknown) => number): unknown; iterations(v: number): unknown
  } | null
  if (collisionForce) {
    const collisionMul = nodeCount <= 3 ? 2.5 : nodeCount <= 10 ? 2.0 : 1.5
    const collisionIters = isInit ? (nodeCount <= 10 ? 6 : 3) : 2
    collisionForce.strength(isInit ? 1.2 : 0.8)
    collisionForce.radius((node: unknown) => getNodeRadius(node as GraphNode3D) * nodeCollisionPadding * collisionMul)
    collisionForce.iterations(collisionIters)
  }

  if (nodeCount <= 5) {
    graph.d3Force('minSeparation', (alpha: number) => {
      const nds = graph.graphData().nodes as GraphNode3D[]
      const minDist = 80
      for (let i = 0; i < nds.length; i++) {
        for (let j = i + 1; j < nds.length; j++) {
          const a = nds[i], b = nds[j]
          if (a.x === undefined || b.x === undefined) continue
          const dx = (b.x ?? 0) - (a.x ?? 0), dy = (b.y ?? 0) - (a.y ?? 0), dz = (b.z ?? 0) - (a.z ?? 0)
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) || 0.001
          if (dist < minDist) {
            const force = (minDist - dist) * alpha * 1.5
            const nx = dx / dist, ny = dy / dist, nz = dz / dist
            a.vx = (a.vx ?? 0) - nx * force; a.vy = (a.vy ?? 0) - ny * force; a.vz = (a.vz ?? 0) - nz * force
            b.vx = (b.vx ?? 0) + nx * force; b.vy = (b.vy ?? 0) + ny * force; b.vz = (b.vz ?? 0) + nz * force
          }
        }
      }
    })
  }

  graph.d3Force('zLayer', (alpha: number) => {
    const nds = graph.graphData().nodes as GraphNode3D[]
    for (const n of nds) {
      const label = getNodeLabel(n)
      const targetZ = label === 'Skill' ? proficiencyToZ(n.properties.proficiency) : 0
      if (n.z !== undefined && targetZ !== undefined) n.vz = (n.vz ?? 0) + (targetZ - n.z) * alpha * 0.15
    }
  })
}

// =============================================================================
// 2. ZoomControls — zoom and fit-view logic
// =============================================================================

/* eslint-disable @typescript-eslint/no-explicit-any */
export function useZoomControls(
  graphInstance: ShallowRef<any>,
  calcFitDistance: (padding?: number) => number,
) {
  /* eslint-enable @typescript-eslint/no-explicit-any */
  function zoomBy(factor: number) {
    const graph = graphInstance.value
    if (!graph) return
    const cam = graph.cameraPosition()
    if (!cam) return
    graph.cameraPosition({ x: cam.x * factor, y: cam.y * factor, z: cam.z * factor }, { x: 0, y: 0, z: 0 }, 400)
  }
  function zoomIn() { zoomBy(0.8) }
  function zoomOut() { zoomBy(1.25) }
  function fitView() {
    const graph = graphInstance.value
    if (!graph) return
    const fitDist = calcFitDistance(1.3)
    graph.cameraPosition({ x: fitDist * 0.6, y: fitDist * 0.5, z: fitDist * 0.8 }, { x: 0, y: 0, z: 0 }, 800)
  }
  return { zoomBy, zoomIn, zoomOut, fitView }
}

// =============================================================================
// 3. NodeTooltip — tooltip state and handlers
// =============================================================================

export interface TooltipNode {
  id: string; name: string; type: string
  position_count?: number; skill_count?: number
  proficiency?: string; category?: string
}

export function useNodeTooltip() {
  const tooltipNode = ref<TooltipNode | null>(null)
  const tooltipX = ref(0)
  const tooltipY = ref(0)
  const tooltipVisible = ref(false)

  let _mouseMoveHandler: ((e: MouseEvent) => void) | null = null

  function createHoverHandler(onHover?: (node: GraphNode3D | null) => void) {
    let _prevHoveredNode: GraphNode3D | null = null
    function _setTextSpriteVisible(nodeObj: GraphNode3D, visible: boolean) {
      const threeObj = (nodeObj as unknown as { __threeObj?: import('three').Object3D }).__threeObj
      if (!threeObj) return
      threeObj.traverse((child) => { if (child.type === 'Sprite' && child.userData.isTextSprite) child.visible = visible })
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (node: any) => {
      const typed = node as GraphNode3D | null
      if (_prevHoveredNode) { _setTextSpriteVisible(_prevHoveredNode, true); _prevHoveredNode = null }
      if (typed) {
        _setTextSpriteVisible(typed, false); _prevHoveredNode = typed
        tooltipNode.value = { id: String(typed.id), name: displayName(typed.properties), type: getNodeLabel(typed), position_count: typed.properties.position_count, skill_count: typed.properties.skill_count, proficiency: typed.properties.proficiency, category: typed.properties.category }
        tooltipVisible.value = true
      } else { tooltipVisible.value = false; tooltipNode.value = null }
      onHover?.(typed)
    }
  }

  function attachMouseMoveListener(container: HTMLElement) {
    _mouseMoveHandler = (e: MouseEvent) => { tooltipX.value = e.clientX; tooltipY.value = e.clientY }
    container.addEventListener('mousemove', _mouseMoveHandler)
  }
  function detachMouseMoveListener(container: HTMLElement) {
    if (_mouseMoveHandler) { container.removeEventListener('mousemove', _mouseMoveHandler); _mouseMoveHandler = null }
  }

  return { tooltipNode, tooltipX, tooltipY, tooltipVisible, createHoverHandler, attachMouseMoveListener, detachMouseMoveListener }
}

// =============================================================================
// 4. CameraPresets — camera positioning logic
// =============================================================================

export type CameraPreset = 'overview' | 'domain' | 'position'

/* eslint-disable @typescript-eslint/no-explicit-any */
export function useCameraPresets(
  graphInstance: ShallowRef<any>,
  nodes: () => GraphNode3D[],
) {
  /* eslint-enable @typescript-eslint/no-explicit-any */
  const autoRotate = ref(false)
  let _autoRotateTimer: ReturnType<typeof setTimeout> | null = null

  function calcFitDistance(padding = 1.3): number {
    const ns = nodes()
    if (ns.length === 0) return 400
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minZ = Infinity, maxZ = -Infinity
    for (const n of ns) {
      if (n.x !== undefined) { minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x) }
      if (n.y !== undefined) { minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y) }
      if (n.z !== undefined) { minZ = Math.min(minZ, n.z); maxZ = Math.max(maxZ, n.z) }
    }
    if (minX === Infinity) return Math.max(400, ns.length * 3)
    const extentX = (maxX - minX) / 2, extentY = (maxY - minY) / 2, extentZ = (maxZ - minZ) / 2
    let radius = Math.max(extentX, extentY, extentZ, 50)
    if (ns.length <= 5 && radius < 180) radius = 180
    return radius * padding
  }

  function setCameraPreset(preset: CameraPreset) {
    const graph = graphInstance.value
    if (!graph) return
    const controls = graph.controls()
    if (controls) controls.autoRotate = false
    const fitDist = calcFitDistance()
    const dist = { x: 0, y: 0, z: 0 }
    switch (preset) {
      case 'overview': dist.x = fitDist * 0.7; dist.y = fitDist * 0.5; dist.z = fitDist * 0.9; break
      case 'domain': dist.x = fitDist * 0.5; dist.y = fitDist * 0.7; dist.z = fitDist * 0.6; break
      case 'position': dist.x = fitDist * 0.4; dist.y = fitDist * 0.4; dist.z = fitDist * 0.9; break
    }
    graph.cameraPosition(dist, { x: 0, y: 0, z: 0 }, 1500)
    if (autoRotate.value) _autoRotateTimer = setTimeout(() => { if (controls) controls.autoRotate = true }, 1600)
  }

  function resetCamera() {
    const graph = graphInstance.value
    if (!graph) return
    const fitDist = calcFitDistance(1.5)
    graph.cameraPosition({ x: fitDist * 0.6, y: fitDist * 0.5, z: fitDist * 0.8 }, { x: 0, y: 0, z: 0 }, 1200)
  }

  function toggleAutoRotate() {
    autoRotate.value = !autoRotate.value
    const graph = graphInstance.value
    if (!graph) return
    const controls = graph.controls()
    if (controls) { controls.autoRotate = autoRotate.value; controls.autoRotateSpeed = 0.8; controls.enableDamping = true }
  }

  function clearAutoRotateTimer() { if (_autoRotateTimer) { clearTimeout(_autoRotateTimer); _autoRotateTimer = null } }

  return { autoRotate, setCameraPreset, resetCamera, toggleAutoRotate, clearAutoRotateTimer, calcFitDistance }
}

// =============================================================================
// 5. EvolutionEdges — evolution edge composition and color logic
// =============================================================================

export interface GraphLink3D extends LinkObject<GraphNode3D> {
  type?: string
  properties?: { weight?: number; trend?: 'rising' | 'stable' | 'declining'; similarity?: number; skill_overlap?: string[]; key_gaps?: string[]; evidence_count?: number }
}

const cc = chartColors()

const _EVOLUTION_TREND_COLOR: Record<string, string> = { rising: cc.success, stable: cc.muted, declining: cc.danger }

export function evolutionColor(link: GraphLink3D): string {
  const trend = link.properties?.trend ?? 'stable'
  const base = _EVOLUTION_TREND_COLOR[trend] ?? _EVOLUTION_TREND_COLOR.stable
  const trust = link.properties?.similarity ?? link.properties?.weight ?? 0.5
  const alpha = 0.3 + Math.max(0, Math.min(1, trust)) * 0.7
  return withAlpha(base, alpha)
}

export function composeEvolutionLinks(
  baseLinks: GraphLink3D[], evolutionPaths: GraphLink3D[], visibleNodes: GraphNode3D[], showEvolution: boolean,
): GraphLink3D[] {
  const composed: GraphLink3D[] = [...baseLinks]
  if (!showEvolution || !evolutionPaths?.length) return composed
  const visibleNodeIds = new Set(visibleNodes.map(n => n.id))
  const filtered = evolutionPaths.filter(ev => {
    const srcOk = visibleNodeIds.has(String(ev.source)) || visibleNodeIds.has(typeof ev.source === 'object' ? ev.source.id : '')
    const tgtOk = visibleNodeIds.has(String(ev.target)) || visibleNodeIds.has(typeof ev.target === 'object' ? ev.target.id : '')
    return srcOk && tgtOk
  })
  for (const ev of filtered) composed.push({ source: ev.source, target: ev.target, type: 'EVOLVES_TO', properties: ev.properties })
  return composed
}

// =============================================================================
// 6. GlowTexture — canvas-based radial gradient glow texture
// =============================================================================

const _glowCache = new Map<number, THREE.Texture>()

export function createGlowTexture(hexColor: number, THREE_NS: typeof import('three')): THREE.Texture {
  const cached = _glowCache.get(hexColor)
  if (cached) return cached
  const size = 128
  const canvas = document.createElement('canvas')
  canvas.width = size; canvas.height = size
  const ctx = canvas.getContext('2d')!
  const r = (hexColor >> 16) & 0xff, g = (hexColor >> 8) & 0xff, b = hexColor & 0xff
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.6)`)
  gradient.addColorStop(0.3, `rgba(${r}, ${g}, ${b}, 0.25)`)
  gradient.addColorStop(0.7, `rgba(${r}, ${g}, ${b}, 0.08)`)
  gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`)
  ctx.fillStyle = gradient; ctx.fillRect(0, 0, size, size)
  const texture = new THREE_NS.CanvasTexture(canvas)
  texture.needsUpdate = true
  _glowCache.set(hexColor, texture)
  return texture
}

export function disposeGlowCache() {
  for (const texture of _glowCache.values()) texture.dispose()
  _glowCache.clear()
}
