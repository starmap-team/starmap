/**
 * useNodeThreeObject — Three.js custom node rendering pipeline for 3D force graph.
 *
 * Creates sphere + glow + text sprites for KnowledgeArea, Position, Skill node types.
 * Extracted from Graph3D.vue to decouple the rendering pipeline from the component.
 */
import type { NodeObject } from '3d-force-graph'
import { nodeColor, toThreeHex, displayName } from '@/utils/graphColors'
import { createGlowTexture } from './useGraph3D'
import { createTextSprite } from './useTextSprite'

// ── Types ──
export interface GraphNode3D extends NodeObject {
  labels?: string[]
  color?: string
  properties: {
    name: string
    category?: string
    proficiency?: string
    position_count?: number
    skill_count?: number
    weight?: number
    [key: string]: unknown
  }
}

// ── Node helpers ──
export function getNodeLabel(node: GraphNode3D): string {
  return node.labels?.[0] ?? 'Unknown'
}

// ── UX-03: Proficiency → z-axis layer mapping ──
// Three-tier stratification: 了解=bottom, 熟悉=middle, 精通=top
// Only applies to Skill nodes; KA/Position stay at z=0
const PROFICIENCY_Z: Record<string, number> = {
  '了解': -40,
  '熟悉': 0,
  '精通': 40,
}
const DEFAULT_PROFICIENCY_Z = 0

/** Map proficiency string to z-coordinate for 3D layering. */
export function proficiencyToZ(proficiency?: string): number {
  if (!proficiency) return DEFAULT_PROFICIENCY_Z
  return PROFICIENCY_Z[proficiency] ?? DEFAULT_PROFICIENCY_Z
}

/** Apply z-layering to Skill nodes in a node array (mutates in place). */
export function applyZLayering(nodes: GraphNode3D[]): void {
  for (const n of nodes) {
    if (getNodeLabel(n) === 'Skill') {
      const targetZ = proficiencyToZ(n.properties.proficiency)
 // Only set z if node doesn't already have a position (new nodes)
 // or if the node hasn't been positioned by force simulation yet
      if (n.x === undefined || n.z === undefined) {
        n.z = targetZ
      }
    }
  }
}

/** Node collision padding factor for force simulation */
export const NODE_COLLISION_PADDING = 1.6

// ── LOD setters consumed by `buildNodeThreeObject` ──
// Module-scope so `useNodeThreeObject` (no Vue ref dependency) can read the
// current level-of-detail set by Graph3D.vue. Defaults match the existing
// behaviour (always full detail) so other callers (Login background, etc.)
// are unaffected until Graph3D sets them.
let _shouldShowLabels = true
let _shouldSimplify = false
export function setLODState(shouldShowLabels: boolean, shouldSimplify: boolean): void {
  _shouldShowLabels = shouldShowLabels
  _shouldSimplify = shouldSimplify
}
export function getLODState(): { shouldShowLabels: boolean; shouldSimplify: boolean } {
  return { shouldShowLabels: _shouldShowLabels, shouldSimplify: _shouldSimplify }
}

export function getNodeRadius(node: GraphNode3D): number {
  const label = getNodeLabel(node)
  switch (label) {
    case 'KnowledgeArea': {
      const skills = node.properties.skill_count ?? 1
 // Cap radius growth to prevent oversized nodes that overlap and stick together
      return 6 + Math.min(Math.sqrt(skills) * 2, 14)
    }
    case 'Position':
      return 4 + (node.properties.weight ?? 0.5) * 3.5
    case 'Skill':
      return 2.5 + (node.properties.weight ?? 0.5) * 2.5
    default:
      return 3
  }
}

/**
 * Build a custom Three.js Object3D for a graph node.
 * Creates sphere + halo + glow sprite + text label based on node type.
 *
 * Respects LOD state from `setLODState`:
 * - shouldSimplify (set when nodeCount > 100): skip halo + glow sprite.
 * - shouldShowLabels=false (set when nodeCount > 30): skip text sprite.
 */
export function buildNodeThreeObject(node: NodeObject): import('three').Object3D {
  const n = node as GraphNode3D
  const label = getNodeLabel(n)
  const radius = getNodeRadius(n)
  const color = toThreeHex(n.color ?? nodeColor(label))
  const { shouldShowLabels, shouldSimplify } = getLODState()

  const THREE = (window as unknown as Record<string, unknown>).__THREE as typeof import('three') | undefined
  if (!THREE) {
 // Fallback: return undefined to use default sphere rendering
    return undefined as unknown as import('three').Object3D
  }

  // LOD simplify > 100 nodes: cheaper geometry + no halo/glow
  const segments = shouldSimplify ? 16 : 32
  const geometry = new THREE.SphereGeometry(radius, segments, segments)

  if (label === 'KnowledgeArea') {
    const material = new THREE.MeshPhysicalMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.35,
      transparent: true,
      opacity: 0.75,
      roughness: 0.25,
      metalness: 0.6,
      clearcoat: 0.8,
      clearcoatRoughness: 0.1,
    })
    const mesh = new THREE.Mesh(geometry, material)

    if (!shouldSimplify) {
      const haloGeometry = new THREE.SphereGeometry(radius * 1.4, 24, 24)
      const haloMaterial = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.12,
        depthWrite: false,
        side: THREE.BackSide,
      })
      mesh.add(new THREE.Mesh(haloGeometry, haloMaterial))

      const spriteMaterial = new THREE.SpriteMaterial({
        map: createGlowTexture(color, THREE),
        transparent: true,
        opacity: 0.25,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
      const sprite = new THREE.Sprite(spriteMaterial)
      sprite.scale.set(radius * 5, radius * 5, 1)
      mesh.add(sprite)
    }

    if (shouldShowLabels) {
      const textSprite = createTextSprite(displayName(n.properties), radius, 'domain', THREE)
      textSprite.position.y = radius + 2
      mesh.add(textSprite)
    }

    return mesh as unknown as import('three').Object3D
  }

  if (label === 'Position') {
    const material = new THREE.MeshPhysicalMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.2,
      transparent: true,
      opacity: 0.85,
      roughness: 0.3,
      metalness: 0.5,
      clearcoat: 0.6,
      clearcoatRoughness: 0.15,
    })
    const mesh = new THREE.Mesh(geometry, material)

    if (!shouldSimplify) {
      const haloGeometry = new THREE.SphereGeometry(radius * 1.3, 24, 24)
      const haloMaterial = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.08,
        depthWrite: false,
        side: THREE.BackSide,
      })
      mesh.add(new THREE.Mesh(haloGeometry, haloMaterial))
    }

    if (shouldShowLabels) {
      const textSprite = createTextSprite(displayName(n.properties), radius, 'position', THREE)
      textSprite.position.y = radius + 1.5
      mesh.add(textSprite)
    }

    return mesh as unknown as import('three').Object3D
  }

  if (label === 'Skill') {
    const material = new THREE.MeshPhysicalMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.15,
      transparent: true,
      opacity: 0.9,
      roughness: 0.4,
      metalness: 0.35,
      clearcoat: 0.4,
      clearcoatRoughness: 0.2,
    })
    const mesh = new THREE.Mesh(geometry, material)

    if (!shouldSimplify) {
      const haloGeometry = new THREE.SphereGeometry(radius * 1.2, 24, 24)
      const haloMaterial = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.05,
        depthWrite: false,
        side: THREE.BackSide,
      })
      mesh.add(new THREE.Mesh(haloGeometry, haloMaterial))
    }

    if (shouldShowLabels && radius >= 3) {
      const textSprite = createTextSprite(displayName(n.properties), radius, 'skill', THREE)
      textSprite.position.y = radius + 1.2
      mesh.add(textSprite)
    }

    return mesh as unknown as import('three').Object3D
  }

 // Default fallback for unknown node types
  return new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color })) as unknown as import('three').Object3D
}
