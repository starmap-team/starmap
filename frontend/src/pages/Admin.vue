<script setup lang="ts">
/**
 * 管理后台 — 重设计
 *
 * Tabs (按用户视角的业务环节排序):
 * 0. 业务总览 - 系统健康 KPI + 业务流图谱
 * 1. 内容审核 - 主数据生命周期（position/skill）
 * 2. 演化变更 - 能力演化（trust_score < 0.6 的变更提案）
 * 3. 图谱节点 - Neo4j 节点 CRUD
 * 4. 数据采集 - 爬虫源 + 同步
 * 5. Prompt - LLM 抽取提示词版本
 * 6. 系统 - 用户管理 + 审计日志
 *
 * 每个 Tab 顶部都有 BusinessBanner 横幅说明业务含义，让新用户秒懂。
 */
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Edit, DataAnalysis } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import AdminOverview from '@/components/AdminOverview.vue'
import EvolutionReviewPanel from '@/components/EvolutionReviewPanel.vue'
import ContentReviewPanel from '@/components/ContentReviewPanel.vue'
import GraphNodeEditor from '@/components/GraphNodeEditor.vue'
import BusinessBanner from '@/components/BusinessBanner.vue'
import { useDataSourceStore } from '@/stores/datasource'
import { useGraphNodeStore } from '@/stores/graphNode'
import { useReviewStore } from '@/stores/review'
import PromptManager from '@/components/PromptManager.vue'
import UserManagement from '@/pages/UserManagement.vue'
import DataTruthPanel from '@/components/DataTruthPanel.vue'
import { getSourceNameLabel } from '@/composables/useDataSourceCharts'
import request from '@/api/request'
import {
  ALL_OPTION,
  CATEGORY_LABELS,
  NODE_REVIEW_STATUS_LABELS,
  NODE_REVIEW_STATUS_TAGS,
  NODE_TYPE_LABELS,
} from '@/constants/labels'
import AuditLog from '@/pages/AuditLog.vue'

import { chartColors } from '@/utils/chartTheme'
import { useGraphNodeList, type GraphNodeItem } from '@/composables/useGraphNodeList'
import { useGraphNodeEditor } from '@/composables/useGraphNodeEditor'

// Node label/status maps (from @/constants/labels)
// E3 fix: Neo4j has 6 labels — Skill / Tool / Position / KnowledgeArea /
// Industry / LearningResource. The old map only knew 5 (missing
// KnowledgeArea / Industry / LearningResource), causing the type filter
// to silently exclude them. Add the missing ones.
function nodeTypeLabel(type: string): string { return NODE_TYPE_LABELS[type] ?? type }
function nodeStatusType(status: string): string { return NODE_REVIEW_STATUS_TAGS[status] ?? 'info' }
function nodeStatusLabel(status: string): string { return NODE_REVIEW_STATUS_LABELS[status] ?? status }

const cc = chartColors()
const router = useRouter()

const datasource = useDataSourceStore()
const graphNode = useGraphNodeStore()
const review = useReviewStore()

// ── Tab 导航 ──
//: 业务总览为默认 tab，让新用户第一眼理解系统。
const activeTab = ref('overview')
//: 系统 tab 内部的子 tab（用户管理 / 审计日志）
const systemSubTab = ref('users-list')
// 2026-08-12 (admin 联调): 数据源诊断 banner 类型随报告状态动态化
const dataTruthBannerType = ref<'success' | 'warning' | 'error'>('error')

// Cross-component navigation: AdminFlow / AdminOverview dispatch a
// 'admin:navigate' CustomEvent to switch tabs without prop-drilling.
// P0-AUDIT-FIX (2026-08-13): the previous listener accepted ANY `detail`
// payload as the new active tab — any third-party script / extension could
// dispatch `{detail: 'review'}` and silently switch to the destructive
// review tab. Restrict to a literal union + warn on reject.
// P2 fix (functional-review 2026-08-13): 白名单此前含 flow/graph/review/audit，
// 而这些 pane 不存在（el-tabs 实际 name 为 content-review/evolution/nodes/
// sources/prompts/data-truth/users/audit-log）—— 一旦任何调用方 dispatch
// 旧值，activeTab 指向不存在的 pane → Tab 内容空白。对齐真实 pane 名。
type AdminTab = 'overview' | 'content-review' | 'evolution' | 'nodes' | 'sources' | 'prompts' | 'data-truth' | 'users' | 'audit-log' | 'users-list'
const _ALLOWED_ADMIN_TABS: ReadonlySet<AdminTab> = new Set<AdminTab>([
  'overview', 'content-review', 'evolution', 'nodes', 'sources', 'prompts', 'data-truth', 'users', 'audit-log', 'users-list',
])
function onAdminNavigate(e: Event) {
  const detail = (e as CustomEvent<unknown>).detail
  if (typeof detail === 'string' && (_ALLOWED_ADMIN_TABS as Set<string>).has(detail)) {
    activeTab.value = detail as AdminTab
  } else {
 // Reject payload — log loudly so silent hijack attempts are visible.
    console.warn('[Admin] rejected admin:navigate with non-allow-listed detail:', detail)
  }
}

onMounted(() => {
  window.addEventListener('admin:navigate', onAdminNavigate)
 // Pre-fetch all stores in the background so tab switches feel instant.
  datasource.fetchSources()
 // : 移除旧 ReviewQueue 空队列拉取 —— review_queue 表 0 行且无写入方，
 // fetchAuditQueue 返回空徒增请求；审核走 review-status 状态机
  graphNode.fetchGraphNodes(0, nodePageSize.value)
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
  statusFilter: nodeStatusFilter,    // E4 fix
  currentPage: nodeCurrentPage,
  pageSize: nodePageSize,
  filtered: filteredGraphNodes,
  paged: pagedGraphNodes,
} = useGraphNodeList(computed(() => graphNode.graphNodes as GraphNodeItem[]))

// fix (functional-review 2026-08-13): 图谱节点管理改为服务端分页。
// 此前 fetchGraphNodes 无参调用默认 limit=20，el-pagination :total 用客户端
// 已取回列表长度 → 节点 >20 时后端节点完全不可见不可操作。现在翻页/改页大小
// 时按 offset/limit 重拉后端，:total 用后端 total。
async function onNodePageChange() {
  await graphNode.fetchGraphNodes(
    (nodeCurrentPage.value - 1) * nodePageSize.value,
    nodePageSize.value,
    nodeSearchKeyword.value,
    nodeTypeFilter.value,
  )
}

// fix: 搜索/类型过滤变化时服务端重拉（客户端过滤只是当前页内增强），
// 避免服务端分页下跨页搜索漏匹配。
watch([nodeSearchKeyword, nodeTypeFilter], () => {
  nodeCurrentPage.value = 1
  void onNodePageChange()
})

// Node editor + CRUD actions (extracted — D round 6)
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

// 2026-08-21 (debug 优化): 图谱节点批量操作 —— 勾选列 + 批量通过/批量删除
const nodeSelection = ref<GraphNodeItem[]>([])
const nodeBatchAction = ref(false)

async function handleBatchApproveNodes() {
  if (nodeSelection.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确认批量通过 ${nodeSelection.value.length} 个待审节点？通过后将出现在公开图谱中。`,
      '批量通过',
      { type: 'warning', confirmButtonText: '确认通过', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  nodeBatchAction.value = true
  let ok = 0; let fail = 0
  for (const node of nodeSelection.value) {
    try {
      await graphNode.approveGraphNode(node.id)
      ok++
    } catch { fail++ }
  }
  nodeSelection.value = []
  await onNodePageChange()
  ElMessage[fail === 0 ? 'success' : 'warning'](`批量通过完成: ${ok} 成功, ${fail} 失败`)
  nodeBatchAction.value = false
}

async function handleBatchDeleteNodes() {
  if (nodeSelection.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确认删除选中的 ${nodeSelection.value.length} 个节点？此操作不可恢复。`,
      '批量删除',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  nodeBatchAction.value = true
  let ok = 0; let fail = 0
  for (const node of nodeSelection.value) {
    try {
      await graphNode.deleteGraphNode(node.id)
      ok++
    } catch { fail++ }
  }
  nodeSelection.value = []
  await onNodePageChange()
  ElMessage[fail === 0 ? 'success' : 'warning'](`批量删除完成: ${ok} 成功, ${fail} 失败`)
  nodeBatchAction.value = false
}

// ════════════════════════════════════════════════
// 数据源编辑 (: el-drawer; state + handlers stay inline — coupled to template refs)
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

// E19: 数据源联动操作 — 让用户能立即触发单源同步,并看到真实统计
const syncingSourceId = ref<string | null>(null)
const activatingSourceId = ref<string | null>(null)
// 2026-08-14: 重新启用停用/暂停源（功能缺口修复——此前停用后 UI 无法再启用）
async function handleActivateSource(row: { id: string; name: string }) {
  activatingSourceId.value = row.id
  try {
    const ok = await datasource.activateSource(row.id)
    if (ok) ElMessage.success(`「${row.name}」已启用，恢复活跃`)
    else ElMessage.error(`启用失败: ${datasource.error || '未知错误'}`)
    await datasource.fetchSources()
  } catch (e: unknown) {
    ElMessage.error(`启用失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    activatingSourceId.value = null
  }
}
async function handleTriggerSync(row: { id: string; name: string }) {
  syncingSourceId.value = row.id
  const progressMsg = ElMessage({
    message: `已触发「${row.name}」单源同步,通常 30-90 秒...`,
    type: 'info',
    duration: 0,
  })
  try {
    const result = await datasource.triggerSync(row.id)
    if (!result) {
      ElMessage.error(`同步失败: ${datasource.error || '未知错误'}`)
      return
    }
    await datasource.fetchSources()  // 重新拉取 record_count / avg_q 更新
    ElMessage.success(
      `「${row.name}」同步已启动 (run_id=${(result.run_id ?? '').slice(0, 8)}). ` +
      `完成后 record_count 会更新，新增岗位/技能将进入「内容审核」待审队列。`,
    )
  } catch (e: unknown) {
    ElMessage.error(`同步失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    progressMsg.close()
    syncingSourceId.value = null
  }
}

// 演示数据重置 (设计文档 管理角色刚需) — POST /admin/seed/reset。
// 生产环境后端直接 refused，不做任何写入。
const seedingDemo = ref(false)
async function handleResetDemoData() {
  try {
    await ElMessageBox.confirm(
      '将执行演示数据种子（数据源 / 流水线阶段 / 演化快照 / 技能时序）。生产环境后端会直接拒绝。确认继续？',
      '重置演示数据',
      { type: 'warning', confirmButtonText: '重置', cancelButtonText: '取消' },
    )
  } catch {
    return // 用户取消
  }
  seedingDemo.value = true
  const progressMsg = ElMessage({ message: '正在重置演示数据...', type: 'info', duration: 0 })
  try {
    const res = await request.post<{
      seeded: string[]
      skipped: string[]
      refused: boolean
      message: string
    }>('/admin/seed/reset')
    if (res.refused) {
      ElMessage.error(`拒绝执行: ${res.message}`)
      return
    }
    ElMessage.success(`演示数据重置完成 — 执行 ${res.seeded.length} 个种子, 跳过 ${res.skipped.length} 个`)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '重置失败，请重试')
  } finally {
    progressMsg.close()
    seedingDemo.value = false
  }
}

// 数据源状态语义化 (2026-08-14): inactive 曾误显示为「异常」——现独立为「已停用」
// 2026-08-20 (debug 修复 A3): active 统一为「运行中」——此前 Admin=「活跃」、
// DataSources 页=「运行中」、DataSourceManager=「待机」三套文案。统一与数据源页一致。
const DATASOURCE_STATUS_LABEL: Record<string, string> = {
  active: '运行中',
  paused: '暂停',
  inactive: '已停用',
  error: '异常',
}
const DATASOURCE_STATUS_TYPE: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
  active: 'success',
  paused: 'warning',
  inactive: 'info',
  error: 'danger',
}
function datasourceStatusLabel(s: string): string {
  return DATASOURCE_STATUS_LABEL[s] ?? s
}
function datasourceStatusType(s: string): 'success' | 'warning' | 'info' | 'danger' {
  return DATASOURCE_STATUS_TYPE[s] ?? 'info'
}

// D5: 软删除（停用）数据源 —— DELETE /datasources/{id} → status='inactive'，保留采集历史
async function handleDeactivateSource(row: { id: string; name: string }) {
  try {
    await ElMessageBox.confirm(
      `停用数据源「${row.name}」？将退出爬取/同步调度（历史采集数据保留）。`,
      '停用数据源',
      { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' },
    )
  } catch {
    return  // 用户取消
  }
  const ok = await datasource.deactivateSource(row.id)
  if (ok) ElMessage.success(`「${row.name}」已停用`)
  else ElMessage.error(`停用失败: ${datasource.error || '未知错误'}`)
}

const statsDrawerVisible = ref(false)
const statsDrawerTitle = ref('数据源统计')
const statsMeta = ref<{
  total: number; successful: number; failed: number; avg: number
  all_time_total?: number; last_crawl_at?: string | null; status?: string
} | null>(null)
async function handleShowStats(row: { id: string; name: string }) {
  statsDrawerTitle.value = `数据源统计 — ${row.name}`
  statsDrawerVisible.value = true
  statsMeta.value = null
  await datasource.fetchStats(row.id)
 // E20b fix: load both /stats meta (runs) and /datasources/{id} meta
 // (all-time total + last_crawl + status) so the drawer shows
 // 30-day pipeline runs AND historical accumulated totals.
  try {
 // E20b fix: load both /stats meta (runs) and /datasources/{id} meta
 // (all-time total + last_crawl + status) so the drawer shows
 // 30-day pipeline runs AND historical accumulated totals.
 // 统一走 request 客户端（拦截器自动附加鉴权），替代裸 fetch + 手工 Bearer
    const [statsRaw, srcRaw] = await Promise.all([
      request.get<{ total_runs?: number; successful_runs?: number; failed_runs?: number; avg_records_per_run?: number }>(
        `/datasources/${row.id}/stats`, { params: { period: '30d' } },
      ),
      request.get<{ total_records?: number; last_crawl_at?: string | null; status?: string }>(
        `/datasources/${row.id}`,
      ),
    ])
    statsMeta.value = {
      total: statsRaw.total_runs ?? 0,
      successful: statsRaw.successful_runs ?? 0,
      failed: statsRaw.failed_runs ?? 0,
      avg: statsRaw.avg_records_per_run ?? 0,
      all_time_total: srcRaw.total_records,
      last_crawl_at: srcRaw.last_crawl_at,
      status: srcRaw.status,
    }
  } catch {
    statsMeta.value = null
  }
}

const maxDailyVolume = computed(() => {
  const daily = datasource.stats?.daily_volume ?? []
  return Math.max(1, ...daily.map((d: { count: number }) => d.count))
})

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    const now = Date.now()
    const diff = (now - d.getTime()) / 1000
    if (diff < 60) return '刚刚'
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
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
        <!-- ════════ Tab 0: 业务总览 ( 新增 — 第一眼) ════════ -->
        <el-tab-pane
          label="业务总览"
          name="overview"
        >
          <AdminOverview />
        </el-tab-pane>

        <!-- ════════ Tab 1: 内容审核 ( 主数据生命周期) ════════ -->
        <el-tab-pane
          label="内容审核"
          name="content-review"
        >
          <BusinessBanner
            type="info"
            title="主数据生命周期 — 新发现的内容审核"
            description="当系统从数据源抽取新岗位或技能时，这些内容会先进入待审核状态。审核通过后才会出现在公开图谱中。"
            :meta="[
              { label: '审核对象：岗位、技能' },
              { label: '来源：自动抽取、人工提交' },
            ]"
          />
          <el-card
            shadow="never"
            class="tab-card"
          >
            <ContentReviewPanel />
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 2: 演化变更 ( 能力演化审核) ════════ -->
        <el-tab-pane
          label="演化变更"
          name="evolution"
        >
          <BusinessBanner
            type="warning"
            title="能力演化审核 — 低信任变更需要人工裁决"
            description="系统每周自动分析岗位能力图谱的演化。信任度较低的变更会进入此队列等待人工确认；信任度较高的变更自动更新到图谱。"
            :meta="[
              { label: '审核对象：低信任度演化变更' },
              { label: '频率：每周自动分析' },
            ]"
          />
          <el-card
            shadow="never"
            class="tab-card"
          >
            <EvolutionReviewPanel />
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 3: 图谱节点管理 ════════ -->
        <el-tab-pane
          label="图谱节点"
          name="nodes"
        >
          <BusinessBanner
            type="info"
            title="知识图谱节点直接管理"
            description="直接对知识图谱中的节点进行增删改查操作。修改会立即影响图谱查询。注意：此操作绕过审核流程，请谨慎使用。"
            :meta="[
              { label: '操作：增、删、改、查' },
              { label: '提示：绕过审核流程' },
            ]"
          />
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

            <!-- 搜索 + 过滤 (E3 + E4 fix) -->
            <div class="node-toolbar">
              <el-input
                v-model="nodeSearchKeyword"
                placeholder="搜索节点名称..."
                :prefix-icon="Search"
                clearable
                class="node-search-input"
                size="default"
              />
              <!-- E3 fix: previously only Skill/Position/Domain were listed.
                   Neo4j actually has 6 labels: Skill, Tool, Position,
                   KnowledgeArea, Industry, LearningResource. Add them all
                   so the filter matches real data. -->
              <el-select
                v-model="nodeTypeFilter"
                placeholder="按类型过滤"
                clearable
                class="node-type-filter"
                size="default"
              >
                <el-option
                  :label="ALL_OPTION"
                  value=""
                />
                <el-option
                  v-for="(label, value) in NODE_TYPE_LABELS"
                  :key="value"
                  :label="`${label} (${value})`"
                  :value="value"
                />
              </el-select>
              <!-- E4 fix: previously every node had status="pending" because
                   create_node hard-coded it. Admin could only see pending
                   nodes — no way to filter approved / rejected. Now expose
                   a status filter dropdown. -->
              <el-select
                v-model="nodeStatusFilter"
                placeholder="按状态过滤"
                clearable
                class="node-status-filter"
                size="default"
              >
                <el-option
                  label="全部"
                  value=""
                />
                <el-option
                  label="待审核"
                  value="pending"
                />
                <el-option
                  label="已通过"
                  value="approved"
                />
                <el-option
                  label="已拒绝"
                  value="rejected"
                />
              </el-select>
            </div>

            <!-- 2026-08-21: 节点批量操作工具栏 -->
            <div
              v-if="nodeSelection.length > 0"
              class="node-batch-toolbar"
            >
              <span class="batch-count">已选 {{ nodeSelection.length }} 个节点</span>
              <el-button
                size="small"
                type="success"
                :disabled="nodeBatchAction"
                @click="handleBatchApproveNodes"
              >
                批量通过
              </el-button>
              <el-button
                size="small"
                type="danger"
                :disabled="nodeBatchAction"
                @click="handleBatchDeleteNodes"
              >
                批量删除
              </el-button>
              <el-button
                size="small"
                text
                @click="nodeSelection = []"
              >
                清除选择
              </el-button>
            </div>

            <!-- 节点表格 -->
            <el-table
              v-loading="graphNodesLoading"
              :data="pagedGraphNodes"
              stripe
              size="default"
              row-key="id"
              empty-text="暂无数据"
              @selection-change="(rows: any[]) => nodeSelection = rows"
            >
              <!-- 2026-08-21: 批量操作勾选列 -->
              <el-table-column
                type="selection"
                width="48"
                align="center"
              />
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
                      {{ CATEGORY_LABELS[row.properties.category] ?? row.properties.category }}
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
              v-if="filteredGraphNodes.length || graphNode.total > 0"
              class="node-pagination"
            >
              <el-pagination
                v-model:current-page="nodeCurrentPage"
                v-model:page-size="nodePageSize"
                :total="graphNode.total"
                :page-sizes="[10, 20, 50]"
                layout="total, sizes, prev, pager, next"
                small
                @current-change="onNodePageChange"
                @size-change="onNodePageChange"
              />
            </div>
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 4: 数据源配置 ════════ -->
        <el-tab-pane
          label="数据采集"
          name="sources"
        >
          <BusinessBanner
            type="success"
            title="数据输入 — 爬虫源配置"
            description="管理爬虫数据源（如 SAP、LinkedIn、Boss直聘等），配置权威性评分与启用状态。权威性评分越高，对岗位和技能信任度的影响越大。"
            :meta="[
              { label: '支持类型：官方标准、招聘 JD、技术博客' },
              { label: '可配置：权威性、启用状态' },
            ]"
          />
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
                label="来源名称"
                min-width="120"
              >
                <template #default="{ row }">
                  {{ getSourceNameLabel(row.name) }}
                </template>
              </el-table-column>
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
                    :type="datasourceStatusType(row.status)"
                    size="small"
                    effect="plain"
                  >
                    {{ datasourceStatusLabel(row.status) }}
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
              <!-- Tab5 / 数据采集 联动修复 (用户的"虚假死数据"反馈):
                   添加 最近爬取时间 与 平均质量 列,
                   让 admin 一眼看出哪些源最近真的在跑、哪些没动 -->
              <el-table-column
                label="最近爬取"
                width="160"
                align="center"
              >
                <template #default="{ row }">
                  <span
                    v-if="row.last_crawl_at"
                    class="crawl-time"
                  >
                    {{ formatDate(row.last_crawl_at) }}
                  </span>
                  <el-tag
                    v-else
                    type="warning"
                    size="small"
                    effect="plain"
                  >
                    从未爬取
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                label="平均质量"
                width="100"
                align="center"
              >
                <template #default="{ row }">
                  <!-- D5 (2026-08-15): 0 记录源的质量分是残留值，显示 — 而非误导性百分比 -->
                  <span v-if="row.total_records === 0">—</span>
                  <span
                    v-else
                    :class="['quality-score', (row.avg_quality_score ?? 0) >= 0.6 ? 'good' : (row.avg_quality_score ?? 0) >= 0.3 ? 'mid' : 'bad']"
                  >
                    {{ ((row.avg_quality_score ?? 0) * 100).toFixed(0) }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column
                label="操作"
                width="280"
                align="center"
                fixed="right"
              >
                <template #default="{ row }">
                  <el-button
                    size="small"
                    plain
                    @click="handleEditSource(row)"
                  >
                    编辑
                  </el-button>
                  <!-- E19 联动修复: 一键触发单源同步,让用户验证管线真的能跑
                       (POST /datasources/{id}/sync → 启动 source_sync PipelineRun
                        → 实际调用 spider → 写 jd_raw → 投影到 PG) -->
                  <el-tooltip
                    placement="top"
                    :show-after="200"
                  >
                    <template #content>
                      立即触发一次「单源同步」流水线 (crawl → dedup → clean → import → graph_sync)。
                      通常 30-90 秒。完成后 record_count/avg_quality_score 字段会自动更新。
                      {{ row.has_adapter ? '' : '该源未配置爬虫适配器，后端将拒绝同步。' }}
                    </template>
                    <el-button
                      size="small"
                      type="success"
                      :loading="syncingSourceId === row.id"
                      plain
                      :disabled="!row.has_adapter || syncingSourceId === row.id"
                      @click="handleTriggerSync(row)"
                    >
                      立即同步
                    </el-button>
                  </el-tooltip>
                  <el-button
                    size="small"
                    type="info"
                    plain
                    @click="handleShowStats(row)"
                  >
                    统计
                  </el-button>
                  <template v-if="row.status === 'active'">
                    <el-tooltip
                      placement="top"
                      :show-after="200"
                    >
                      <template #content>
                        停用数据源，退出爬取/同步调度（历史数据保留）
                      </template>
                      <el-button
                        size="small"
                        type="danger"
                        plain
                        @click="handleDeactivateSource(row)"
                      >
                        停用
                      </el-button>
                    </el-tooltip>
                  </template>
                  <template v-else>
                    <!-- 2026-08-14: 启用按钮——修复"停用后无法再启用"功能缺口 -->
                    <el-tooltip
                      placement="top"
                      :show-after="200"
                    >
                      <template #content>
                        {{ row.status === 'paused' ? '恢复该数据源为活跃（重新加入爬取/同步调度）' : '重新启用该数据源（恢复为活跃）' }}
                      </template>
                      <el-button
                        size="small"
                        type="success"
                        :loading="activatingSourceId === row.id"
                        @click="handleActivateSource(row)"
                      >
                        启用
                      </el-button>
                    </el-tooltip>
                  </template>
                </template>
              </el-table-column>
            </el-table>

            <!-- 统计抽屉 (E19: 显示 /datasources/{id}/stats 真实聚合结果) -->
            <!-- 2026-08-21 (debug 修复): append-to-body 防滚动容器内偏移 -->
            <el-drawer
              v-model="statsDrawerVisible"
              :title="statsDrawerTitle"
              direction="rtl"
              size="520px"
              append-to-body
            >
              <div
                v-if="datasource.loading"
                class="stats-loading"
              >
                <el-icon class="is-loading">
                  <svg viewBox="0 0 1024 1024"><path
                    fill="currentColor"
                    d="M512 64a32 32 0 0 0 32 32v128a32 32 0 0 0-64 0V96a32 32 0 0 0 32-32zm0 768a32 32 0 0 0 32 32v64a32 32 0 1 1-64 0v-64a32 32 0 0 0 32-32zm448-408H832a32 32 0 0 1 0-64h128a32 32 0 1 1 0 64zM192 416H64a32 32 0 0 1 0-64h128a32 32 0 1 1 0 64zM794.912 165.952l-90.624 90.496a32 32 0 0 1-45.248-45.248l90.624-90.496a32 32 0 1 1 45.248 45.248zM274.912 685.952l-90.496 90.624a32 32 0 1 1-45.248-45.248l90.496-90.624a32 32 0 0 1 45.248 45.248zM704 480a224 224 0 1 0-448 0 224 224 0 1 0 448 0z"
                  /></svg>
                </el-icon>
                <span>加载中...</span>
              </div>
              <div
                v-else-if="datasource.stats"
                class="stats-body"
              >
                <div class="stats-summary">
                  <div class="stat-tile">
                    <div class="stat-tile-label">
                      累计记录 (30天)
                    </div>
                    <div class="stat-tile-value">
                      {{ datasource.stats.total_count ?? 0 }}
                    </div>
                  </div>
                  <div class="stat-tile">
                    <div class="stat-tile-label">
                      累计总记录
                    </div>
                    <!-- E20b: also surface the DataSourceRecord.total_records
                         (all-time). This catches historical records that
                         pre-date the sub_breakdown field and are not
                         attributed to any recent pipeline run. -->
                    <div class="stat-tile-value">
                      {{ statsMeta?.all_time_total ?? '—' }}
                    </div>
                  </div>
                  <div class="stat-tile">
                    <div class="stat-tile-label">
                      日均记录
                    </div>
                    <div class="stat-tile-value">
                      {{ datasource.stats.avg_daily_count ?? 0 }}
                    </div>
                  </div>
                </div>
                <div
                  class="stats-summary"
                  style="margin-top: 8px;"
                >
                  <div class="stat-tile">
                    <div class="stat-tile-label">
                      成功 / 失败 run
                    </div>
                    <div class="stat-tile-value">
                      <span style="color: rgb(5,150,105);">
                        {{ statsMeta?.successful ?? 0 }}
                      </span>
                      <span style="color: var(--muted-foreground); font-size: 14px; margin: 0 4px;">/</span>
                      <span style="color: rgb(220,38,38);">
                        {{ statsMeta?.failed ?? 0 }}
                      </span>
                    </div>
                  </div>
                  <div class="stat-tile">
                    <div class="stat-tile-label">
                      最近爬取
                    </div>
                    <div
                      class="stat-tile-value"
                      style="font-size: 14px;"
                    >
                      {{ formatDate(statsMeta?.last_crawl_at) }}
                    </div>
                  </div>
                  <div class="stat-tile">
                    <div class="stat-tile-label">
                      当前状态
                    </div>
                    <div
                      class="stat-tile-value"
                      style="font-size: 14px;"
                    >
                      <el-tag
                        v-if="statsMeta?.status"
                        :type="statsMeta.status === 'active' ? 'success' : statsMeta.status === 'inactive' ? 'info' : 'warning'"
                        size="small"
                        effect="plain"
                      >
                        <!-- 2026-08-20 (debug 修复 A2): inactive 曾落入兜底"异常"（红色），
                             与表格"已停用"矛盾。现独立为"已停用"。 -->
                        {{ statsMeta.status === 'active' ? '运行中' : statsMeta.status === 'paused' ? '暂停' : statsMeta.status === 'inactive' ? '已停用' : '异常' }}
                      </el-tag>
                      <span v-else>—</span>
                    </div>
                  </div>
                </div>
                <h4 class="stats-h">
                  每日采集量 (最近 30 天)
                </h4>
                <div class="stats-chart">
                  <div
                    v-for="bar in (datasource.stats.daily_volume ?? []).slice(-30)"
                    :key="bar.date"
                    class="bar-row"
                  >
                    <span class="bar-date">{{ bar.date.slice(5) }}</span>
                    <div class="bar-track">
                      <div
                        class="bar-fill"
                        :style="{ width: Math.min(100, (bar.count / Math.max(1, maxDailyVolume)) * 100) + '%' }"
                      />
                    </div>
                    <span class="bar-count">{{ bar.count }}</span>
                  </div>
                </div>
              </div>
            </el-drawer>

            <!-- 编辑抽屉 (: 统一用 el-drawer) -->
            <!-- 2026-08-21 (debug 修复): append-to-body —— 列表偏下方打开抽屉时，
                 默认渲染在组件内跟随滚动容器偏移，导致窗口上方无法操作 -->
            <el-drawer
              v-model="editDialogVisible"
              title="编辑数据源"
              direction="rtl"
              size="400px"
              append-to-body
              :modal-class="'drawer-edit-modal'"
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
          <BusinessBanner
            type="info"
            title="抽取质量控制 — 提示词管理"
            description="管理技能抽取所用的提示词模板，支持版本管理与方案对比。提示词质量直接影响抽取结果的可信度。"
            :meta="[
              { label: '功能：版本管理、A/B 测试' },
            ]"
          />
          <el-card
            shadow="never"
            class="tab-card"
          >
            <PromptManager />
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 6: 数据源诊断（ P0 — 跨模块 KPI 口径审计） ════════ -->
        <el-tab-pane
          label="数据源诊断"
          name="data-truth"
        >
          <BusinessBanner
            :type="dataTruthBannerType"
            title="数据一致性诊断 — 跨模块 KPI 口径审计"
            description="每个统计数字都有多层来源相互校验。当数字不一致时，说明底层数据存在孤儿节点或同步缺失。"
            :meta="[
              { label: '健康标准：差异 < 1% 良好，1–10% 警告，> 10% 严重' },
              { label: '覆盖：岗位数、技能数、关系数' },
            ]"
          />
          <el-card
            shadow="never"
            class="tab-card"
          >
            <DataTruthPanel
              @overall-status="(s: string) => { dataTruthBannerType = s === 'ok' ? 'success' : s === 'warn' ? 'warning' : 'error' }"
            />
          </el-card>
        </el-tab-pane>

        <!-- ════════ Tab 7: 系统（用户 + 审计） ════════ -->
        <el-tab-pane
          label="系统"
          name="users"
        >
          <BusinessBanner
            type="warning"
            title="系统运维 — 用户管理与安全审计"
            description="管理用户权限（管理员与普通用户）与系统安全审计日志（登录、授权、敏感操作）。审计日志独立于内容审核，是安全追溯机制。"
            :meta="[
              { label: '功能：用户管理、审计日志、演示数据' },
            ]"
          />
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
            <el-tab-pane
              label="演示数据"
              name="demo-seed"
            >
              <BusinessBanner
                type="info"
                title="演示数据一键重置"
                description="一键加载演示数据（数据源、流水线阶段、演化快照、技能时序）。生产环境后端直接拒绝。"
                :meta="[
                  { label: '仅演示环境可用' },
                  { label: '影响：覆盖现有数据' },
                ]"
              />
              <el-card
                shadow="never"
                class="tab-card"
              >
                <el-button
                  type="warning"
                  :loading="seedingDemo"
                  @click="handleResetDemoData"
                >
                  {{ seedingDemo ? '重置中...' : '重置演示数据' }}
                </el-button>
              </el-card>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>
      </el-tabs>

      <!-- Graph Node Editor Dialog (E5 final: align-center + max-height
           + overflow-y: auto to handle small viewports without
           clipping the dialog above the visible area) -->
      <GraphNodeEditor
        v-model:visible="editorVisible"
        :edit-data="editingNode"
        @submit="handleNodeSubmit"
      />
    </div>
  </MainLayout>
</template>

<style scoped>
/* 2026-08-21: 节点批量操作工具栏 */
.node-batch-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding: 6px 10px;
  background: var(--bg-muted, #f1f5f9);
  border-radius: 6px;
}
.node-batch-toolbar .batch-count {
  font-size: 12px;
  color: #475569;
  margin-right: 4px;
}

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

.admin-tabs :deep(.el-tabs__nav-wrap) {
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}

.admin-tabs :deep(.el-tabs__nav-wrap)::after {
  height: 1px;
}

.admin-tabs :deep(.el-tabs__nav) {
  white-space: nowrap;
  min-width: max-content;
}

.admin-tabs :deep(.el-tabs__item) {
  padding: 0 16px;
  font-size: 13px;
}

@media (max-width: 1280px) {
  .admin-tabs :deep(.el-tabs__item) {
    padding: 0 10px;
    font-size: 12px;
  }
}

.tab-card {
  border-radius: var(--radius-xl);
}

.tab-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* ── Business description banner — migrated to BusinessBanner component (+) ── */

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

/* E19: 数据源联动样式 */
.crawl-time {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  white-space: nowrap;
}
.quality-score {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.quality-score.good { color: rgb(5, 150, 105); }
.quality-score.mid  { color: rgb(217, 119, 6); }
.quality-score.bad  { color: rgb(220, 38, 38); }

.stats-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 20px;
  color: var(--muted-foreground);
}
.stats-summary {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}
.stat-tile {
  background: var(--muted);
  border-radius: 8px;
  padding: 12px 16px;
}
.stat-tile-label {
  font-size: 12px;
  color: var(--muted-foreground);
}
.stat-tile-value {
  font-size: 22px;
  font-weight: 800;
  margin-top: 4px;
  font-variant-numeric: tabular-nums;
}
.stats-h {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--foreground);
}
.stats-chart {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 360px;
  overflow-y: auto;
}
.bar-row {
  display: grid;
  grid-template-columns: 50px 1fr 60px;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}
.bar-date {
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
}
.bar-track {
  background: var(--muted);
  height: 10px;
  border-radius: 4px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: var(--primary);
  transition: width 0.3s;
}
.bar-count {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

/* Layout utilities */
.mt-3 { margin-top: var(--space-3); }
</style>
