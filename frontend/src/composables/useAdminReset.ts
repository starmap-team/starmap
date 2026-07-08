/**
 * Admin reset action — extracted from Admin.vue (Phase 7 D round 12).
 * Owns the "reset to demo data" flow: ElMessageBox confirm + store call + refresh all panels.
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { useAdminStore } from '@/stores/admin'

type AdminStore = ReturnType<typeof useAdminStore>

export function useAdminReset(store: AdminStore): {
  handleReset: () => Promise<void>
} {
  async function handleReset(): Promise<void> {
    try {
      await ElMessageBox.confirm(
        '确认重置系统数据？将重新加载标准数据集，此操作不可撤销。',
        '重置数据',
        { confirmButtonText: '确认重置', cancelButtonText: '取消', type: 'warning' },
      )
      await store.resetToDemo()
      ElMessage.success('数据已重置')
      store.fetchSources()
      store.fetchAuditQueue()
      store.fetchGraphNodes()
    } catch { /* cancel */ }
  }

  return { handleReset }
}
