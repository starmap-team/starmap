/**
 * useForceConfig — Force engine tuning and collision configuration for 3D force graph.
 *
 * Extracted from Graph3D.vue to decouple the force simulation configuration
 * from the component.
 */
import type { GraphNode3D, NODE_COLLISION_PADDING as _PAD } from './useNodeThreeObject'

/** Force configuration parameters based on node count */
export interface ForceConfig {
  chargeStrength: number
  linkDist: number
  linkStrength: number
  alphaDecay: number
  velocityDecay: number
  warmupTicks: number
  cooldownTicks: number
}

/**
 * Calculate force configuration parameters based on node count.
 */
export function calcForceConfig(nodeCount: number): ForceConfig {
  return {
    chargeStrength: nodeCount > 200 ? -400 : nodeCount > 100 ? -250 : -150,
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

/**
 * Apply force configuration to a 3d-force-graph instance.
 * Sets charge, link, center, and collision forces.
 */
export function applyForceConfig(
  graph: GraphInstance,
  nodeCount: number,
  nodeCollisionPadding: number,
  getNodeRadius: (node: GraphNode3D) => number,
  isInit: boolean = true,
): void {
  const cfg = calcForceConfig(nodeCount)

  // Charge force
  const chargeForce = graph.d3Force('charge') as unknown as { strength(v: number): unknown; distanceMax(v: number): unknown } | null
  if (chargeForce) {
    chargeForce.strength(cfg.chargeStrength)
    chargeForce.distanceMax(isInit ? 1200 : 600)
  }

  // Link force
  const linkForce = graph.d3Force('link') as unknown as { distance(v: number): unknown; strength(v: number): unknown } | null
  if (linkForce) {
    linkForce.distance(cfg.linkDist)
    linkForce.strength(cfg.linkStrength)
  }

  // Center force
  const centerForce = graph.d3Force('center') as unknown as { strength(v: number): unknown } | null
  if (centerForce) {
    centerForce.strength(isInit ? 0.008 : 0.02)
  }

  // Collision force
  const collisionForce = graph.d3Force('collision') as unknown as {
    strength(v: number): unknown
    radius(v: (node: unknown) => number): unknown
    iterations(v: number): unknown
  } | null
  if (collisionForce) {
    collisionForce.strength(isInit ? 1.2 : 0.8)
    collisionForce.radius((node: unknown) => {
      const n = node as GraphNode3D
      return getNodeRadius(n) * nodeCollisionPadding * (isInit ? 1.5 : 1)
    })
    collisionForce.iterations(isInit ? 3 : 2)
  }
}
