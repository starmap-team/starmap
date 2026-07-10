/// <reference types="vite/client" />

// d3-force-3d has no @types package — declare the subset we use
declare module 'd3-force-3d' {
  import type { Simulation, SimulationLinkDatum, SimulationNodeDatum } from 'd3-force'

  export function forceSimulation<NodeDatum extends SimulationNodeDatum = SimulationNodeDatum>(
    nodes?: NodeDatum[]
  ): Simulation<NodeDatum, SimulationLinkDatum<NodeDatum>>

  export function forceLink<NodeDatum extends SimulationNodeDatum = SimulationNodeDatum, LinkDatum extends SimulationLinkDatum<NodeDatum> = SimulationLinkDatum<NodeDatum>>(
    links?: LinkDatum[]
  ): import('d3-force').ForceLink<NodeDatum, LinkDatum>

  export function forceManyBody<NodeDatum extends SimulationNodeDatum = SimulationNodeDatum>(): import('d3-force').Force<NodeDatum, undefined>

  export function forceCenter<NodeDatum extends SimulationNodeDatum = SimulationNodeDatum>(
    x?: number, y?: number, z?: number
  ): import('d3-force').Force<NodeDatum, undefined>

  export function forceCollide<NodeDatum extends SimulationNodeDatum = SimulationNodeDatum>(
    radius?: number | ((node: NodeDatum) => number)
  ): import('d3-force').Force<NodeDatum, undefined>

  export function forceRadial<NodeDatum extends SimulationNodeDatum = SimulationNodeDatum>(
    radius?: number, x?: number, y?: number, z?: number
  ): import('d3-force').Force<NodeDatum, undefined>

  export function forceX<NodeDatum extends SimulationNodeDatum = SimulationNodeDatum>(
    x?: number
  ): import('d3-force').Force<NodeDatum, undefined>

  export function forceY<NodeDatum extends SimulationNodeDatum = SimulationNodeDatum>(
    y?: number
  ): import('d3-force').Force<NodeDatum, undefined>

  export function forceZ<NodeDatum extends SimulationNodeDatum = SimulationNodeDatum>(
    z?: number
  ): import('d3-force').Force<NodeDatum, undefined>
}

// three.js — @types/three is installed; remove the manual any-typed shim.
// If typecheck fails in environments where @types/three is not resolvable
// (e.g. Docker volume mount), add `"skipLibCheck": true` to tsconfig instead.
// Keeping a minimal fallback for the dynamic-import window exposure pattern:
declare module 'three' {
  export * from 'three/src/Three.js'
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_USE_MSW: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
