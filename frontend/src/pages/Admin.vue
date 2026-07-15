<script setup lang="ts">
/**
 * 管理后台 — Phase 24 重设计
 *
 * Tabs (按用户视角的业务环节排序):
 *  0. 业务总览   - 系统健康 KPI + 业务流图谱
 *  1. 内容审核   - Phase 23 主数据生命周期（position/skill）
 *  2. 演化变更   - §5.2 能力演化（trust_score < 0.6 的变更提案）
 *  3. 图谱节点   - Neo4j 节点 CRUD
 *  4. 数据采集   - 爬虫源 + 同步
 *  5. Prompt     - LLM 抽取提示词版本
 *  6. 系统       - 用户管理 + 审计日志
 *
 * 每个 Tab 顶部都有 el-alert 横幅说明业务含义，让新用户秒懂。
 */
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search, Plus, Edit, DataAnalysis } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import AdminOverview from '@/components/AdminOverview.vue'
import ReviewQueuePanel from '@/components/ReviewQueuePanel.vue'
import ContentReviewPanel from '@/components/ContentReviewPanel.vue'
import GraphNodeEditor from '@/components/GraphNodeEditor.vue'
import { useDataSourceStore } from '@/stores/datasource'
import { useAuditStore } from '@/stores/audit'
import { useGraphNodeStore } from '@/stores/graphNode'
import { useReviewStore } from '@/stores/review'
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
const review = useReviewStore()

// ── Tab 导航 ──
// Phase 24: 业务总览为默认 tab，让新用户第一眼理解系统。
const activeTab = ref('overview')
// Phase 24: 系统 tab 内部的子 tab（用户管理 / 审计日志）
const systemSubTab = ref('users-list')

// Cross-component navigation: AdminFlow / AdminOverview dispatch a
// 'admin:navigate' CustomEvent to switch tabs without prop-drilling.
function onAdminNavigate(e: Event) {
  const tab = (e as CustomEvent<string>).detail
  activeTab.value = tab
}

onMounted(() => {
  window.addEventListener('admin:navigate', onAdminNavigate)
  // Pre-fetch all stores in the background so tab switches feel instant.
  datasource.fetchSources()
  audit.fetchAuditQueue()
  graphNode.fetchGraphNodes()
  review.fetchStats().catch(() => null)
})

onUnmounted(() => {
  window.removeEventListener('admin:navigate', onAdminNavigate)
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
            StarMap 业务闭环的运营控制台 — 6 大功能区覆盖采集 → 抽取 → 图谱 → 审核 → 匹配 → 学习
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
        <!-- ════════ Tab 0: 业务总览 (Phase 24 新增 — 第一眼) ════════ -->
        <el-tab-pane
          label="业务总览"
          name="overview"
        >
          <AdminOverview />
        </el-tab-pane>

        <!-- ════════ Tab 1: 内容审核 (Phase 23 主数据生命周期) ════════ -->
        <el-tab-pane
          label="内容审核"
          name="content-review"
        >
          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="tab-description"
          >
            <template #title>主数据生命周期 — 新发现的内容审核</template>
            <p>当系统从数据源抽取新岗位/技能、或在 /extract/jd 提取新内容时，
            这些实体进入"待审核"状态。审核通过后才会出现在公开图谱中。</p>
            <p class="tab-meta">后端: <code>/admin/review-items</code> · 数据源: <code>position_records.review_status</code> + <code>skill_records.review_status</code></p>
          </el-alert>
          <el-card
            shadow="never"
            class="tab-card"
          >
            <ContentReviewPanel />
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 2: 演化变更 (§5.2 能力演化审核) ════════ -->
        <el-tab-pane
          label="演化变更"
          name="evolution"
        >
          <el-alert
            type="warning"
            :closable="false"
            show-icon
            class="tab-description"
          >
            <template #title>§5.2 能力演化审核 — 低信任变更需要人工裁决</template>
            <p>系统每周自动分析岗位能力图谱的演化（§5.2）。对于信任度低于 0.6 的
            变更提案，会自动写入此队列等待人工确认是否更新图谱。信任度 ≥ 0.6 的
            变更直接入图谱。</p>
            <p class="tab-meta">后端: <code>/admin/review-queue</code> · 触发: <code>EvolutionOrchestrator._save_changelog</code> (trust_score &lt; 0.6)</p>
          </el-alert>
          <el-card
            shadow="never"
            class="tab-card"
          >
            <ReviewQueuePanel />
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 3: 图谱节点管理 ════════ -->
        <el-tab-pane
          label="图谱节点"
          name="nodes"
        >
          <el-alert
            type="primary"
            :closable="false"
            show-icon
            class="tab-description"
          >
            <template #title>Neo4j 图谱节点直接管理</template>
            <p>直接对 Neo4j 知识图谱中的节点进行 CRUD 操作。修改会立即影响图谱查询。
            注意：此 tab 绕过审核流程，请谨慎操作。</p>
            <p class="tab-meta">后端: <code>/admin/graph/nodes</code> · 数据源: Neo4j</p>
          </el-alert>
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

        <!-- ════════ Tab 4: 数据源配置 ════════ -->
        <el-tab-pane
          label="数据采集"
          name="sources"
        >
          <el-alert
            type="success"
            :closable="false"
            show-icon
            class="tab-description"
          >
            <template #title>§5.2 数据输入 — 爬虫源配置</template>
            <p>管理爬虫数据源（SAP、LinkedIn、Boss直聘等），配置权威性评分、启用状态。
            权威性评分直接影响信任度驱动的图谱构建策略（§7.1）。</p>
            <p class="tab-meta">后端: <code>/datasources</code> · 数据源: <code>datasources</code> 表</p>
          </el-alert>
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

        <!-- ════════ Tab 5: Prompt 管理 ════════ -->
        <el-tab-pane
          label="Prompt 工程"
          name="prompts"
        >
          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="tab-description"
          >
            <template #title>§7.2 幻觉防控 — LLM 抽取提示词管理</template>
            <p>管理 LLM 抽取技能的提示词模板，支持版本控制和 A/B 测试。
            提示词质量直接影响信任度评分和幻觉率。</p>
            <p class="tab-meta">后端: <code>/admin/prompts</code></p>
          </el-alert>
          <el-card
            shadow="never"
            class="tab-card"
          >
            <PromptManager />
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 6: 系统（用户 + 审计） ════════ -->
        <el-tab-pane label="系统" name="users">
          <el-alert
            type="warning"
            :closable="false"
            show-icon
            class="tab-description"
          >
            <template #title>系统运维 — 用户管理与安全审计</template>
            <p>用户权限管理（admin / 普通用户）和系统级安全审计日志（登录、授权、敏感操作）。
            审计日志与"内容审核"无关，是独立的安全追溯机制。</p>
            <p class="tab-meta">后端: <code>/admin/users</code>, <code>/admin/audit-events</code></p>
          </el-alert>
          <el-tabs
            v-model="systemSubTab"
            class="sub-tabs"
          >
            <el-tab-pane
              label="用户管理"
              name="users-list"
            >
              <UserManagement />
            </el-tab-pane>
            <el-tab-pane
              label="审计日志"
              name="audit-log"
            >
              <AuditLog />
            </el-tab-pane>
          </el-tabs>
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

/* ── Business description banner (Phase 24) ── */
.tab-description {
  margin-bottom: var(--space-3);
  border-radius: var(--radius-lg);
}
.tab-description :deep(p) {
  margin: 4px 0 0;
  font-size: var(--font-size-sm);
  color: var(--foreground);
  line-height: 1.5;
}
.tab-description .tab-meta {
  margin-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
.tab-description code {
  background: var(--muted);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 11px;
}

.sub-tabs {
  margin-top: var(--space-2);
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
