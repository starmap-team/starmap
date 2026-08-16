/**
 * forceConfig — 3d-force-graph 力导参数常量
 *
 * 2026-08-13: (M1 全景图谱) Plan 01-04 Task 2 — 抽 Graph3D.vue:240-280
 * force config 常量 (warmupTicks / cooldownTime / d3AlphaDecay 等)。
 *
 * 既有代码中 force config 是 const 赋值;本文件仅抽常量,不在 composable 层修改。
 */
export interface ForceConfig {
  warmupTicks: number
  cooldownTime: number
  d3AlphaDecay: number
  d3VelocityDecay: number
  linkWidth: number
  nodeResolution: number
}

export const DEFAULT_FORCE_CONFIG: ForceConfig = {
  warmupTicks: 100,
  cooldownTime: 2000,
  d3AlphaDecay: 0.0228,
  d3VelocityDecay: 0.4,
  linkWidth: 1,
  nodeResolution: 8,
}

// LOD 阈值 (沿 useGraphLOD.ts:22 默认值,3D 镜像)
export const LOD_3D_THRESHOLDS = {
  hideLabelsAbove: 30,
  simplifyAbove: 100,
} as const