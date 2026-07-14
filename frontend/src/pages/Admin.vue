<script setup lang="ts">
/**
 * 管理后台 — 增强版
 * Tabs: 审核队列 | 图谱节点管理 | 数据源配置
 * 新增: 图谱节点 CRUD + ReviewQueuePanel 集成
 */
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search, Plus, Edit, DataAnalysis } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import ReviewQueuePanel from '@/components/ReviewQueuePanel.vue'
import ContentReviewPanel from '@/components/ContentReviewPanel.vue'
import GraphNodeEditor from '@/components/GraphNodeEditor.vue'
import { useDataSourceStore } from '@/stores/datasource'
import { useAuditStore } from '@/stores/audit'
import { useGraphNodeStore } from '@/stores/graphNode'
import PromptManager from '@/components/PromptManager.vue'
import UserManagement from '@/pages/UserManagement.vue'
import AuditLog from '@/pages/AuditLog.vue'

import { chartColors } from '@/utils/chartTheme'
import { useGraphNodeList, type GraphNodeItem } from '@/composables/useGraphNodeList'
import { useGraphNodeEditor } from '@/composables/useGraphNodeEditor'
import { nodeTypeLabel, nodeStatusType, nodeStatusLabel } from '@/composables/useGraphNodeLabels'

const cc = chartColors()
const router = useRouter()

const datasource = useDataSourceStore()
const audit = useAuditStore()
const graphNode = useGraphNodeStore()

// ── Tab 导航 ──
const activeTab = ref('audit')

onMounted(() => {
  datasource.fetchSources()
  audit.fetchAuditQueue()
  graphNode.fetchGraphNodes()
})

// ════════════════════════════════════════════════
// 图谱节点管理
// ════════════════════════════════════════════════

const graphNodesLoading = computed(() => graphNode.loading)
const {
  searchKeyword: nodeSearchKeyword,
  typeFilter: nodeTypeFilter,
  currentPage: nodeCurrentPage,
  pageSize: nodePageSize,
  filtered: filteredGraphNodes,
  paged: pagedGraphNodes,
} = useGraphNodeList(computed(() => graphNode.graphNodes as GraphNodeItem[]))

// Node editor + CRUD actions (extracted — Phase 7 D round 6)
const {
  editorVisible,
  editingNode,
  handleCreateNode,
  handleEditNode,
  handleNodeSubmit,
  handleDeleteNode,
  handleApproveNode,
  handleRejectNode,
} = useGraphNodeEditor(graphNode)

// ════════════════════════════════════════════════
// 数据源编辑 (D-12: el-drawer; state + handlers stay inline — coupled to template refs)
// ════════════════════════════════════════════════

const editDialogVisible = ref(false)
const editSaving = ref(false)
const editingSource = ref<{ id: string; name: string; authority_score: number; status: string } | null>(null)
function handleEditSource(row: { id: string; name: string; authority_score: number; status: string }) {
  editingSource.value = { id: row.id, name: row.name, authority_score: Math.round(row.authority_score * 100), status: row.status }
  editDialogVisible.value = true
}
async function handleSaveSource() {
  if (!editingSource.value) return
  editSaving.value = true
  try {
    // authority_score slider is 0-100, backend stores 0-1
    const payload = { authority_score: editingSource.value.authority_score / 100 }
    await datasource.updateSource(editingSource.value.id, payload)
    editDialogVisible.value = false
    ElMessage.success('保存成功')
    await datasource.fetchSources()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败，请重试')
  } finally {
    editSaving.value = false
  }
}
</script>

<template>
  <MainLayout>
    <div class="admin-page animate-fade-in">
      <div class="page-header">
        <div>
          <h2>管理后台</h2>
          <p class="page-desc">
            人工审核、图谱节点管理、数据源配置、Prompt管理
          </p>
        </div>
        <el-button
          type="info"
          plain
          :icon="DataAnalysis"
          @click="router.push('/quality')"
        >
          查看质量报告
        </el-button>
      </div>

      <!-- Tab 导航 -->
      <el-tabs
        v-model="activeTab"
        class="admin-tabs"
      >
        <!-- ════════ Tab 1: 审核队列 (legacy evolution-changelog items) ════════ -->
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

        <!-- ════════ Tab 2: 内容审核 (Phase 23 position/skill review) ════════ -->
        <el-tab-pane
          label="内容审核"
          name="content-review"
        >
          <el-card
            shadow="never"
            class="tab-card"
          >
            <ContentReviewPanel />
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 3: 图谱节点管理 ════════ -->
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
              empty-text="暂无数据"
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
              :data="datasource.sources"
              stripe
              size="default"
              empty-text="暂无数据"
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
                    :color="row.authority_score >= 0.8 ? cc.success : row.authority_score >= 0.6 ? cc.warning : cc.danger"
                  />
                </template>
              </el-table-column>
              <el-table-column
                label="状态"
                width="80"
                align="center"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="row.status === 'active' ? 'success' : row.status === 'paused' ? 'warning' : 'danger'"
                    size="small"
                    effect="plain"
                  >
                    {{ row.status === 'active' ? '活跃' : row.status === 'paused' ? '暂停' : '异常' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                label="记录数"
                width="90"
                align="center"
              >
                <template #default="{ row }">
                  {{ row.total_records ?? 0 }}
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

            <!-- 编辑抽屉 (D-12: 统一用 el-drawer) -->
            <el-drawer
              v-model="editDialogVisible"
              title="编辑数据源"
              direction="rtl"
              size="400px"
            >
              <el-form
                v-if="editingSource"
                label-width="80px"
              >
                <el-form-item label="名称">
                  <el-input
                    :model-value="editingSource.name"
                    disabled
                  />
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
                <el-button @click="editDialogVisible = false">
                  取消
                </el-button>
                <el-button
                  type="primary"
                  :loading="editSaving"
                  @click="handleSaveSource"
                >
                  保存
                </el-button>
              </template>
            </el-drawer>
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 4: Prompt 管理 ════════ -->
        <el-tab-pane
          label="Prompt 管理"
          name="prompts"
        >
          <el-card
            shadow="never"
            class="tab-card"
          >
            <PromptManager />
          </el-card>
	        </el-tab-pane>

	        <!-- Tab 5: 用户管理 -->
        <el-tab-pane label="用户管理" name="users">
          <el-card shadow="never" class="tab-card">
            <UserManagement />
          </el-card>
        </el-tab-pane>

        <!-- Tab 6: 审计日志 -->
        <el-tab-pane label="审计日志" name="audit-log">
          <el-card shadow="never" class="tab-card">
            <AuditLog />
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
  display: flex;
  align-items: center;
  justify-content: space-between;
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

/* Layout utilities */
.mt-3 { margin-top: var(--space-3); }
</style>
