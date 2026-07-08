/**
 * LearningCenter user actions — update skill status + add recommendation to plan.
 * Extracted from LearningCenter.vue (Phase 7 D round 5).
 * Toast messages owned by ElMessage — kept inline for ops visibility.
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { useLearningStore } from '@/stores/learning'

type LearningStore = ReturnType<typeof useLearningStore>

export interface PlanRef {
  value: { plan_id: string; position: string } | null
}

export interface UseLearningActionsApi {
  handleUpdateStatus: (skill: string, status: string) => Promise<void>
  handleAddToPlan: (rec: { skill: string; priority: string }) => Promise<void>
}

export function useLearningActions(
  store: LearningStore,
  currentPlan: PlanRef,
): UseLearningActionsApi {
  async function handleUpdateStatus(skill: string, status: string): Promise<void> {
    if (!currentPlan.value) {
      ElMessage.warning('请先创建学习计划')
      return
    }
    try {
      await store.updateProgress(currentPlan.value.plan_id, skill, status)
      const statusLabel = status === 'mastered' ? '已掌握' : status === 'in_progress' ? '学习中' : '未开始'
      ElMessage.success(`已更新「${skill}」状态为 ${statusLabel}`)
    } catch {
      // error handled by store
    }
  }

  // ponytail: D-08 single-plan; D-09 POST /learning/plan; D-06 plan_id→localStorage
  async function handleAddToPlan(rec: { skill: string; priority: string }): Promise<void> {
    try {
      if (currentPlan.value) {
        await ElMessageBox.confirm(
          `已有学习计划「${currentPlan.value.position}」，是否用「${rec.skill}」覆盖？`,
          '覆盖学习计划',
          { confirmButtonText: '确认覆盖', cancelButtonText: '取消', type: 'warning' },
        )
        await store.createPlan({
          position: rec.skill,
          skills: [{ skill: rec.skill, importance: 'required', gap_level: '完全缺失' }],
        })
        ElMessage.success('已创建新学习计划')
      } else {
        await store.createPlan({
          position: rec.skill,
          skills: [{ skill: rec.skill, importance: 'required', gap_level: '完全缺失' }],
        })
        ElMessage.success(`「${rec.skill}」已加入学习计划`)
      }
    } catch (e: unknown) {
      if (e === 'cancel' || e === 'close') return
      ElMessage.error(e instanceof Error ? e.message : '加入计划失败')
    }
  }

  return { handleUpdateStatus, handleAddToPlan }
}
