<script setup lang="ts">
/**
 * 管理后台 — 增强版
 * Tabs: 审核队列 | 图谱节点管理 | 数据源配置 | 演示数据管理
 * 新增: 图谱节点 CRUD + ReviewQueuePanel 集成
 */
import { onMounted, ref, computed, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete, Plus, Edit } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import ReviewQueuePanel from '@/components/ReviewQueuePanel.vue'
import GraphNodeEditor from '@/components/GraphNodeEditor.vue'
import { useAdminStore } from '@/stores/admin'
import request from '@/api/request'

const admin = useAdminStore()

// ── Tab 导航 ──
const activeTab = ref('audit')

onMounted(() => {
  admin.fetchSources()
  admin.fetchAuditQueue()
  fetchGraphNodes()
})

// ════════════════════════════════════════════════
// 图谱节点管理
// ════════════════════════════════════════════════

interface GraphNodeItem {
  id: string
  type: string
  name: string
  properties: Record<string, any>
  status: 'pending' | 'approved' | 'rejected'
  created_at?: string
}

const graphNodes = ref<GraphNodeItem[]>([])
const graphNodesLoading = ref(false)
const nodeSearchKeyword = ref('')
const nodeTypeFilter = ref('')
const nodeCurrentPage = ref(1)
const nodePageSize = ref(10)

const filteredGraphNodes = computed(() => {
  let list = graphNodes.value
  if (nodeSearchKeyword.value) {
    const kw = nodeSearchKeyword.value.toLowerCase()
    list = list.filter(n => n.name.toLowerCase().includes(kw))
  }
  if (nodeTypeFilter.value) {
    list = list.filter(n => n.type === nodeTypeFilter.value)
  }
  return list
})

const pagedGraphNodes = computed(() => {
  const start = (nodeCurrentPage.value - 1) * nodePageSize.value
  return filteredGraphNodes.value.slice(start, start + nodePageSize.value)
})

async function fetchGraphNodes() {
  graphNodesLoading.value = true
  try {
    const data = await request.get('/admin/graph/nodes') as any
    graphNodes.value = data.items ?? []
  } catch {
    graphNodes.value = []
  } finally {
    graphNodesLoading.value = false
  }
}

// Node editor
const editorVisible = ref(false)
const editingNode = ref<{ id?: string; type: string; name: string; properties: Record<string, any> } | null>(null)

function handleCreateNode() {
  editingNode.value = null
  editorVisible.value = true
}

function handleEditNode(node: GraphNodeItem) {
  editingNode.value = {
    id: node.id,
    type: node.type,
    name: node.name,
    properties: { ...node.properties },
  }
  editorVisible.value = true
}

async function handleNodeSubmit(data: any) {
  try {
    if (data.id) {
      // Update
      await request.put(`/admin/graph/nodes/${data.id}`, data)
      ElMessage.success('节点已更新')
    } else {
      // Create
      await request.post('/admin/graph/nodes', data)
      ElMessage.success('节点已提交审核')
    }
    fetchGraphNodes()
  } catch (e: any) {
    ElMessage.error(e?.message ?? '操作失败')
  }
}

async function handleDeleteNode(node: GraphNodeItem) {
  try {
    await ElMessageBox.confirm(`确认删除节点「${node.name}」？`, '删除确认', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await request.delete(`/admin/graph/nodes/${node.id}`)
    ElMessage.success('节点已删除')
    fetchGraphNodes()
  } catch { /* 取消或失败 */ }
}

async function handleApproveNode(node: GraphNodeItem) {
  try {
    await request.post(`/admin/graph/nodes/${node.id}/approve`)
    ElMessage.success('节点已审核通过')
    fetchGraphNodes()
  } catch (e: any) {
    ElMessage.error(e?.message ?? '审核失败')
  }
}

async function handleRejectNode(node: GraphNodeItem) {
  try {
    await request.post(`/admin/graph/nodes/${node.id}/reject`)
    ElMessage.warning('节点已拒绝')
    fetchGraphNodes()
  } catch (e: any) {
    ElMessage.error(e?.message ?? '拒绝失败')
  }
}

function nodeTypeLabel(type: string): string {
  const map: Record<string, string> = { Skill: '技能', Position: '岗位', Domain: '领域', Tool: '工具', Certificate: '证书' }
  return map[type] ?? type
}

function nodeStatusType(status: string): string {
  const map: Record<string, string> = { approved: 'success', rejected: 'danger', pending: 'warning' }
  return map[status] ?? 'info'
}

function nodeStatusLabel(status: string): string {
  const map: Record<string, string> = { approved: '已通过', rejected: '已拒绝', pending: '待审核' }
  return map[status] ?? status
}

// ════════════════════════════════════════════════
// 数据源编辑（原有逻辑保留）
// ════════════════════════════════════════════════

const editDialogVisible = ref(false)
const editingSource = ref<{ id: number; name: string; authority_score: number } | null>(null)
function handleEditSource(row: any) {
  editingSource.value = { id: row.id, name: row.name, authority_score: row.authority_score }
  editDialogVisible.value = true
}
function handleSaveSource() {
  if (!editingSource.value) return
  const idx = admin.sources.findIndex(s => s.id === editingSource.value!.id)
  if (idx !== -1) {
    admin.sources[idx] = { ...admin.sources[idx], name: editingSource.value.name, authority_score: editingSource.value.authority_score }
  }
  editDialogVisible.value = false
  ElMessage.success('数据源已更新')
}

// ── 重置数据 ──
async function handleReset() {
  try {
    await ElMessageBox.confirm(
      '确认重置系统数据？将重新加载标准数据集，此操作不可撤销。',
      '重置数据',
      { confirmButtonText: '确认重置', cancelButtonText: '取消', type: 'warning' }
    )
    await admin.resetToDemo()
    ElMessage.success('数据已重置')
    admin.fetchSources()
    admin.fetchAuditQueue()
    fetchGraphNodes()
  } catch { /* 取消 */ }
}
</script>

<template>
  <MainLayout>
    <div class="admin-page animate-fade-in">
      <div class="page-header">
        <div>
          <h2>管理后台</h2>
          <p class="page-desc">
            人工审核、图谱节点管理、数据源配置与演示数据管理
          </p>
        </div>
      </div>

      <!-- Tab 导航 -->
      <el-tabs
        v-model="activeTab"
        class="admin-tabs"
      >
        <!-- ════════ Tab 1: 审核队列 ════════ -->
        <el-tab-pane
          label="审核队列"
          name="audit"
        >
          <el-card
            shadow="never"
            class="tab-card"
          >
            <ReviewQueuePanel />
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 2: 图谱节点管理 ════════ -->
        <el-tab-pane
          label="图谱节点管理"
          name="nodes"
        >
          <el-card
            shadow="never"
            class="tab-card"
          >
            <template #header>
              <div class="tab-card-header">
                <span class="section-label">图谱节点 CRUD</span>
                <el-button
                  type="primary"
                  size="small"
                  :icon="Plus"
                  @click="handleCreateNode"
                >
                  新建节点
                </el-button>
              </div>
            </template>

            <!-- 搜索 + 过滤 -->
            <div class="node-toolbar">
              <el-input
                v-model="nodeSearchKeyword"
                placeholder="搜索节点名称..."
                :prefix-icon="Search"
                clearable
                class="node-search-input"
                size="default"
              />
              <el-select
                v-model="nodeTypeFilter"
                placeholder="按类型过滤"
                clearable
                class="node-type-filter"
                size="default"
              >
                <el-option
                  label="全部"
                  value=""
                />
                <el-option
                  label="技能"
                  value="Skill"
                />
                <el-option
                  label="岗位"
                  value="Position"
                />
                <el-option
                  label="领域"
                  value="Domain"
                />
              </el-select>
            </div>

            <!-- 节点表格 -->
            <el-table
              v-loading="graphNodesLoading"
              :data="pagedGraphNodes"
              stripe
              size="default"
            >
              <el-table-column
                prop="id"
                label="ID"
                width="120"
                align="center"
              >
                <template #default="{ row }">
                  <span class="node-id">{{ row.id }}</span>
                </template>
              </el-table-column>
              <el-table-column
                label="类型"
                width="85"
                align="center"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="row.type === 'Skill' ? 'success' : row.type === 'Position' ? 'info' : 'warning'"
                    size="small"
                    effect="dark"
                  >
                    {{ nodeTypeLabel(row.type) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                prop="name"
                label="名称"
                min-width="140"
                sortable
              />
              <el-table-column
                label="状态"
                width="90"
                align="center"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="nodeStatusType(row.status)"
                    size="small"
                    effect="plain"
                  >
                    {{ nodeStatusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                label="属性"
                min-width="160"
              >
                <template #default="{ row }">
                  <span class="node-props">
                    <template v-if="row.properties?.category">
                      {{ row.properties.category }}
                    </template>
                    <template v-if="row.properties?.proficiency">
                      · {{ row.properties.proficiency }}
                    </template>
                    <template v-if="row.properties?.level">
                      · {{ row.properties.level }}
                    </template>
                    <template v-if="!row.properties?.category && !row.properties?.proficiency && !row.properties?.level">
                      —
                    </template>
                  </span>
                </template>
              </el-table-column>
              <el-table-column
                label="操作"
                width="240"
                align="center"
                fixed="right"
              >
                <template #default="{ row }">
                  <el-button
                    size="small"
                    :icon="Edit"
                    plain
                    @click="handleEditNode(row)"
                  >
                    编辑
                  </el-button>
                  <el-button
                    v-if="row.status === 'pending'"
                    size="small"
                    type="success"
                    plain
                    @click="handleApproveNode(row)"
                  >
                    通过
                  </el-button>
                  <el-button
                    v-if="row.status === 'pending'"
                    size="small"
                    type="warning"
                    plain
                    @click="handleRejectNode(row)"
                  >
                    拒绝
                  </el-button>
                  <el-button
                    size="small"
                    type="danger"
                    plain
                    @click="handleDeleteNode(row)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <!-- 空状态 -->
            <div
              v-if="!filteredGraphNodes.length && !graphNodesLoading"
              class="empty-state"
            >
              无图谱节点数据
            </div>

            <!-- 分页 -->
            <div
              v-if="filteredGraphNodes.length"
              class="node-pagination"
            >
              <el-pagination
                v-model:current-page="nodeCurrentPage"
                v-model:page-size="nodePageSize"
                :total="filteredGraphNodes.length"
                :page-sizes="[10, 20, 50]"
                layout="total, sizes, prev, pager, next"
                small
              />
            </div>
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 3: 数据源配置 ════════ -->
        <el-tab-pane
          label="数据源配置"
          name="sources"
        >
          <el-card
            shadow="never"
            class="tab-card"
          >
            <template #header>
              <span class="section-label">数据源配置</span>
            </template>
            <el-table
              :data="admin.sources"
              stripe
              size="default"
            >
              <el-table-column
                prop="name"
                label="来源名称"
                min-width="120"
              />
              <el-table-column
                prop="source_type"
                label="类型"
                width="80"
                align="center"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="row.source_type === 'official' ? 'success' : 'info'"
                    size="small"
                    effect="dark"
                  >
                    {{ row.source_type === 'official' ? '官方' : '聚合' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                label="权威性"
                width="100"
                align="center"
              >
                <template #default="{ row }">
                  <el-progress
                    :percentage="Math.round(row.authority_score * 100)"
                    :stroke-width="8"
                    :color="row.authority_score >= 0.8 ? '#67c23a' : row.authority_score >= 0.6 ? '#e6a23c' : '#f56c6c'"
                  />
                </template>
              </el-table-column>
              <el-table-column
                label="操作"
                width="100"
                align="center"
              >
                <template #default="{ row }">
                  <el-button
                    size="small"
                    plain
                    @click="handleEditSource(row)"
                  >
                    编辑
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <!-- 编辑对话框 -->
            <el-dialog
              v-model="editDialogVisible"
              title="编辑数据源"
              width="400px"
            >
              <el-form
                v-if="editingSource"
                label-width="80px"
              >
                <el-form-item label="名称">
                  <el-input v-model="editingSource.name" />
                </el-form-item>
                <el-form-item label="权威分">
                  <el-slider
                    v-model="editingSource.authority_score"
                    :min="0"
                    :max="100"
                    :step="1"
                  />
                </el-form-item>
              </el-form>
              <template #footer>
                <el-button @click="editDialogVisible = false">取消</el-button>
                <el-button
                  type="primary"
                  @click="handleSaveSource"
                >
                  保存
                </el-button>
              </template>
            </el-dialog>
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 4: 演示数据管理 ════════ -->
        <el-tab-pane
          label="演示数据管理"
          name="demo"
        >
          <el-card
            shadow="never"
            class="tab-card"
          >
            <template #header>
              <span class="section-label">演示数据管理</span>
            </template>
            <p class="demo-desc">
              重置为演示种子数据将覆盖当前所有数据，包括岗位、技能、图谱节点与关系。此功能用于演示场景重置（§16.5）。
            </p>
            <el-button
              type="danger"
              class="mt-3"
              :icon="Delete"
              @click="handleReset"
            >
              重置为演示数据
            </el-button>
          </el-card>
        </el-tab-pane>
      </el-tabs>

      <!-- Graph Node Editor Dialog -->
      <GraphNodeEditor
        v-model:visible="editorVisible"
        :edit-data="editingNode"
        @submit="handleNodeSubmit"
      />
    </div>
  </MainLayout>
</template>

<style scoped>
.admin-page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: var(--space-5);
}

.page-header h2 {
  font-size: var(--font-size-3xl);
  font-weight: 600;
  color: var(--foreground);
  margin: 0 0 4px;
}

.page-desc {
  color: var(--muted-foreground);
  font-size: var(--font-size-base);
  margin: 0;
}

/* ── Tabs ── */
.admin-tabs {
  margin-top: var(--space-2);
}

.tab-card {
  border-radius: var(--radius-xl);
}

.tab-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-label {
  font-weight: 600;
  font-size: var(--font-size-base);
}

/* ── Node management toolbar ── */
.node-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}

.node-search-input {
  width: 240px;
}

.node-type-filter {
  width: 130px;
}

.node-id {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

.node-props {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

.node-pagination {
  margin-top: var(--space-4);
  display: flex;
  justify-content: center;
}

.empty-state {
  text-align: center;
  padding: var(--space-6);
  color: var(--muted-foreground);
}

.demo-desc {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
  line-height: 1.8;
  margin: 0;
}

/* Layout utilities */
.mt-3 { margin-top: var(--space-3); }
</style>
