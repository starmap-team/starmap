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
export type { DataSource as DataSourceDetail } from './pipelineRun'

// ── Re-export types from pipelineConfig ──
export type { PipelineSchedule, PipelineConfig } from './pipelineConfig'

// ── Re-export constants from pipelineConfig ──
export { STAGE_LABELS, ALL_STAGE_NAMES } from './pipelineConfig'

// ── Backward-compatible combined store ──
// Merges both sub-stores so existing consumers using usePipelineStore() continue to work
import { usePipelineRunStore } from './pipelineRun'
import { usePipelineConfigStore } from './pipelineConfig'

export const usePipelineStore = () => {
  const run = usePipelineRunStore()
  const config = usePipelineConfigStore()

  return {
    // Run store
    runs: run.runs,
    pipelineStatus: run.pipelineStatus,
    currentRun: run.pipelineStatus?.current_run ?? null,
    runLoading: run.loading,
    runError: run.error,
    stages: run.stages,
    dataQuality: run.dataQuality,
    dataSources: run.dataSources,
    fetchRuns: run.fetchRuns,
    fetchStatus: run.fetchStatus,
    fetchStages: run.fetchStages,
    fetchDataQuality: run.fetchDataQuality,
    fetchDataSources: run.fetchDataSources,
    triggerPipeline: run.triggerPipeline,
    cancelRun: run.cancelRun,
    retryStage: run.retryStage,
    resumeRun: run.resumeRun,
    handlePipelineEvent: run.handlePipelineEvent,
    handleQualityAlert: run.handleQualityAlert,
    handleMilestone: run.handleMilestone,
    handleExtractionComplete: run.handleExtractionComplete,
    // Config store
    schedules: config.schedules,
    config: config.config,
    configLoading: config.configLoading,
    configError: config.error,
    fetchSchedules: config.fetchSchedules,
    createSchedule: config.createSchedule,
    updateSchedule: config.updateSchedule,
    deleteSchedule: config.deleteSchedule,
    triggerSchedule: config.triggerSchedule,
    fetchConfig: config.fetchConfig,
    updateConfig: config.updateConfig,
    // Combined loading/error (unwrapped to plain boolean/string for template binding)
    loading: run.loading || config.configLoading,
    error: run.error || config.error,
  }
}
