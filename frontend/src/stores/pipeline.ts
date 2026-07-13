/**
 * 数据流水线 Store — barrel re-export
 * 拆分为 pipelineRun (运行状态) + pipelineConfig (调度/配置)
 * 本文件保持向后兼容：所有原有 import 路径继续有效
 */

// ── Re-export stores ──
export { usePipelineRunStore } from './pipelineRun'
export { usePipelineConfigStore } from './pipelineConfig'

// ── Re-export types from pipelineRun ──
export type {
  PipelineStage,
  PipelineRun,
  PipelineStatus,
  DataQualityMetrics,
  DataMilestone,
  ExtractionComplete,
} from './pipelineRun'
export type { QualityAlert } from './pipelineRun'
export type { DataSourceDetail as DataSource } from './pipelineRun'

// ── Re-export types from pipelineConfig ──
export type { PipelineSchedule, PipelineConfig } from './pipelineConfig'

// ── Re-export constants from pipelineConfig ──
export { STAGE_LABELS, ALL_STAGE_NAMES } from './pipelineConfig'

// ── Backward-compatible combined store ──
// Merges both sub-stores so existing consumers using usePipelineStore() continue to work
import { usePipelineRunStore } from './pipelineRun'
import { usePipelineConfigStore } from './pipelineConfig'

export const usePipelineStore = () => ({
  ...usePipelineRunStore(),
  ...usePipelineConfigStore(),
})
