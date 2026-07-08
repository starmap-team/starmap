/**
 * Admin graph node editor state + CRUD actions — extracted from Admin.vue (Phase 7 D round 6).
 * Owns: editorVisible + editingNode refs and 6 handlers (create/edit/submit/delete/approve/reject).
 * Toast messages owned by ElMessage — kept inline for ops visibility.
 */
import { ref, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { useAdminStore } from '@/stores/admin'
import type { GraphNodeItem } from '@/composables/useGraphNodeList'

type AdminStore = ReturnType<typeof useAdminStore>

export interface NodeEditorData {
  id?: string
  type: string
  name: string
  properties: Record<string, unknown>
}

export interface GraphNodeEditorApi {
  editorVisible: Ref<boolean>
  editingNode: Ref<NodeEditorData | null>
  handleCreateNode: () => void
  handleEditNode: (node: GraphNodeItem) => void
  handleNodeSubmit: (data: NodeEditorData) => Promise<void>
  handleDeleteNode: (node: GraphNodeItem) => Promise<void>
  handleApproveNode: (node: GraphNodeItem) => Promise<void>
  handleRejectNode: (node: GraphNodeItem) => Promise<void>
}

export function useGraphNodeEditor(store: AdminStore): GraphNodeEditorApi {
  const editorVisible: Ref<boolean> = ref(false)
  const editingNode: Ref<NodeEditorData | null> = ref(null)

  function handleCreateNode(): void {
    editingNode.value = null
    editorVisible.value = true
  }

  function handleEditNode(node: GraphNodeItem): void {
    editingNode.value = {
      id: node.id,
      type: node.type,
      name: node.name,
      properties: { ...node.properties },
    }
    editorVisible.value = true
  }

  async function handleNodeSubmit(data: NodeEditorData): Promise<void> {
    try {
      if (data.id) {
        await store.updateGraphNode(data.id, { ...data })
        ElMessage.success('节点已更新')
      } else {
        await store.createGraphNode({ ...data })
        ElMessage.success('节点已提交审核')
      }
    } catch (e: unknown) {
      ElMessage.error(e instanceof Error ? e.message : '操作失败')
    }
  }

  async function handleDeleteNode(node: GraphNodeItem): Promise<void> {
    try {
      await ElMessageBox.confirm(`确认删除节点「${node.name}」？`, '删除确认', {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      })
      await store.deleteGraphNode(node.id)
      ElMessage.success('节点已删除')
    } catch { /* 取消或失败 */ }
  }

  async function handleApproveNode(node: GraphNodeItem): Promise<void> {
    try {
      await store.approveGraphNode(node.id)
      ElMessage.success('节点已审核通过')
    } catch (e: unknown) {
      ElMessage.error(e instanceof Error ? e.message : '审核失败')
    }
  }

  async function handleRejectNode(node: GraphNodeItem): Promise<void> {
    try {
      await store.rejectGraphNode(node.id)
      ElMessage.warning('节点已拒绝')
    } catch (e: unknown) {
      ElMessage.error(e instanceof Error ? e.message : '拒绝失败')
    }
  }

  return {
    editorVisible,
    editingNode,
    handleCreateNode,
    handleEditNode,
    handleNodeSubmit,
    handleDeleteNode,
    handleApproveNode,
    handleRejectNode,
  }
}
