/**
 * 定时调度 CRUD composable（ Plan 03 Task 8 实际迁移）。
 *
 * 从 usePipelineMonitor.ts 抽出调度相关状态与操作：
 * 调度对话框状态、scheduleForm、create/delete/toggle/trigger。
 */
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePipelineConfigStore } from '@/stores/pipelineConfig'
import type { PipelineSchedule } from '@/stores/pipelineConfig'

export interface SchedulesOptions {
 /** 调度触发成功后刷新全页面（loadAll） */
  onAfterTrigger?: () => Promise<void> | void
}

export function useSchedules(options: SchedulesOptions = {}) {
  const configStore = usePipelineConfigStore()
  const scheduleLoading = ref(false)
  const scheduleDialogVisible = ref(false)
  const scheduleForm = ref({
    name: '',
    cron_expression: '0 2 * * *',
    run_type: 'incremental' as 'full' | 'incremental',
    selected_stages: null as string[] | null,
    selected_sources: null as string[] | null,
    enabled: true,
  })

  function openScheduleDialog() {
    scheduleForm.value = { name: '', cron_expression: '0 2 * * *', run_type: 'incremental', selected_stages: null, selected_sources: null, enabled: true }
    scheduleDialogVisible.value = true
  }

  async function handleCreateSchedule() {
    scheduleLoading.value = true
    try {
      await configStore.createSchedule(scheduleForm.value)
      scheduleDialogVisible.value = false
      ElMessage.success(`定时调度「${scheduleForm.value.name}」已创建`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '创建失败'
      ElMessage.error(`创建失败：${msg}`)
    } finally {
      scheduleLoading.value = false
    }
  }

  async function handleDeleteSchedule(id: string) {
    try {
      await ElMessageBox.confirm('确定删除此定时调度？', '确认')
      scheduleLoading.value = true
      await configStore.deleteSchedule(id)
      ElMessage.success('已删除')
    } catch {
 /* cancelled — schedules list already refreshed by store */
    } finally {
      scheduleLoading.value = false
    }
  }

  async function handleTriggerSchedule(schedule: PipelineSchedule) {
    scheduleLoading.value = true
    try {
      await configStore.triggerSchedule(schedule.id)
 // 调度触发了 pipeline run，需要刷新全页面状态
      await options.onAfterTrigger?.()
      ElMessage.success(`调度「${schedule.name}」已触发执行`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '触发失败'
      ElMessage.error(`触发调度失败：${msg}`)
    } finally {
      scheduleLoading.value = false
    }
  }

  async function handleToggleSchedule(schedule: PipelineSchedule) {
    try {
      await configStore.updateSchedule(schedule.id, { ...schedule, enabled: !schedule.enabled })
      ElMessage.success(schedule.enabled ? '调度已禁用' : '调度已启用')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '操作失败'
      ElMessage.error(`操作失败：${msg}`)
    }
  }

  return {
    scheduleLoading,
    scheduleDialogVisible,
    scheduleForm,
    openScheduleDialog,
    handleCreateSchedule,
    handleDeleteSchedule,
    handleTriggerSchedule,
    handleToggleSchedule,
  }
}
