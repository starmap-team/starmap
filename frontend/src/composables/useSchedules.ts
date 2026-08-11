/**
 * useSchedules hook（D-03 Task 8 拆分骨架）
 *
 * 当前为占位接口契约，调度逻辑保留在 usePipelineMonitor.ts 中。
 * 下一步：实际迁移 schedules CRUD 操作（list/create/update/delete/trigger）。
 */
import { ref } from 'vue'
import type { Ref } from 'vue'

export interface Schedule {
  id: string
  name: string
  cron: string
  enabled: boolean
}

export interface SchedulesApi {
  schedules: Ref<Schedule[]>
  loading: Ref<boolean>
  load: () => Promise<void>
  create: (data: { name: string; cron: string }) => Promise<void>
  update: (id: string, data: { name?: string; cron?: string; enabled?: boolean }) => Promise<void>
  remove: (id: string) => Promise<void>
  trigger: (id: string) => Promise<void>
}

/**
 * 当前实现：返回空 hook 桩。
 * 未来 Task 8/Task 11 完成后，PipelineMonitor 改用此 hook 替代内联调度 CRUD。
 */
export function useSchedules(): SchedulesApi {
  const schedules = ref<Schedule[]>([]) as Ref<Schedule[]>
  const loading = ref(false)

  const noop = async () => {
    /* no-op */
  }

  return {
    schedules,
    loading,
    load: noop,
    create: noop as SchedulesApi['create'],
    update: noop,
    remove: noop,
    trigger: noop,
  }
}