/**
 * useTriggerPipeline hook（D-03 Task 8 拆分骨架）
 *
 * 当前为占位接口契约，触发逻辑仍保留在 usePipelineMonitor.ts 中。
 * 下一步：实际迁移 trigger / cancel / retry / resume / force-advance / force-reset 操作。
 */
import { ref } from 'vue'
import type { Ref } from 'vue'

export interface TriggerPipelineApi {
  loading: Ref<boolean>
  trigger: (stages: string[], runType?: string) => Promise<void>
  cancel: (runId: string) => Promise<void>
  retry: (runId: string) => Promise<void>
  resume: (runId: string) => Promise<void>
  forceAdvance: (runId: string) => Promise<void>
  forceReset: (runId: string) => Promise<void>
}

/**
 * 当前实现：返回空 hook 桩，由 PipelineMonitor 继续使用 usePipelineMonitor.ts。
 * 未来 Task 8 完成后，PipelineMonitor 改用此 hook 替代内联操作。
 */
export function useTriggerPipeline(): TriggerPipelineApi {
  // 占位：返回 no-op refs 以满足接口契约
  const loading = ref(false)

  const noop = async () => {
    /* no-op */
  }

  return {
    loading,
    trigger: noop as TriggerPipelineApi['trigger'],
    cancel: noop,
    retry: noop,
    resume: noop,
    forceAdvance: noop,
    forceReset: noop,
  }
}