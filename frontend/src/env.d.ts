/// <reference types="vite/client" />

// d3-force-3d has no @types package — declare it as any
declare module 'd3-force-3d' {
  const d3Force3d: any
  export default d3Force3d
  export const forceSimulation: any
  export const forceLink: any
  export const forceManyBody: any
  export const forceCenter: any
  export const forceCollide: any  // Used by @antv/layout
  export const forceRadial: any   // Used by @antv/layout
  export const forceX: any
  export const forceY: any
  export const forceZ: any
}

// three.js types may not be resolvable in some environments (e.g. when running
// typecheck inside a Docker container where the volume mount hides @types/three).
// We only need `any` for the dynamic import used to expose THREE on window.
declare module 'three' {
  const THREE: any
  export default THREE
  export const Scene: any
  export const PerspectiveCamera: any
  export const WebGLRenderer: any
  export const Mesh: any
  export const SphereGeometry: any
  export const MeshBasicMaterial: any
  export const Color: any
  export const Group: any
  export const CanvasTexture: any
  export const Sprite: any
  export const SpriteMaterial: any
  export const AmbientLight: any
  export const DirectionalLight: any
  export const Vector3: any
  export const BoxGeometry: any
  export const MeshPhongMaterial: any
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

