<script setup lang="ts">
/**
 * ContentReviewPanel — review workflow for position + skill entities.
 *
 * Replaces the legacy "review_queue" workflow (which only stored evolution
 * changelog items) with a unified admin queue that shows ALL pending
 * positions and skills awaiting approval. Each row can be approved
 * (with optional reason) or rejected (reason required).
 *
 * State machine: draft → pending_review → approved | rejected
 * (see app.services.review_service on the backend)
 */
import { onMounted, ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Close, EditPen, RefreshRight } from '@element-plus/icons-vue'
import request from '@/api/request'
import { useReviewStore, type ReviewEntityType, type ReviewItem, type ReviewStatus } from '@/stores/review'
import { ALL_OPTION, POSITION_REVIEW_STATUS_LABELS, REVIEW_SOURCE_LABELS } from '@/constants/labels'

const reviewStore = useReviewStore()

const entityTypeFilter = ref<'' | ReviewEntityType>('')
const statusFilter = ref<'' | ReviewStatus>('pending_review')
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const selection = ref<ReviewItem[]>([])

// 2026-08-21: 批量操作改调后端批量端点（一次请求替代逐条循环），
// 按 entity_type 分组（position/skill 分开调）
async function callBatch(action: 'approve' | 'reject', reason?: string) {
  const byType = new Map<ReviewEntityType, string[]>()
  for (const item of selection.value) {
    const t = item.entity_type as ReviewEntityType
    if (!byType.has(t)) byType.set(t, [])
    byType.get(t)!.push(item.entity_id)
  }
  let ok = 0; let fail = 0
  for (const [type, ids] of byType) {
    try {
      const res = await request.post('/admin/review/batch', {
        entity_type: type,
        entity_ids: ids,
        action,
        reason: reason || null,
      }) as { ok: number; fail: number }
      ok += res.ok ?? 0
      fail += res.fail ?? 0
    } catch { fail += ids.length }
  }
  selection.value = []
  await reviewStore.fetchItems()
  await reviewStore.fetchStats()
  const label = action === 'approve' ? '批准' : '拒绝'
  ElMessage[fail === 0 ? 'success' : 'warning'](`${label}完成: ${ok} 成功, ${fail} 失败`)
}

async function batchApprove() {
  if (selection.value.length === 0) return
 // 2026-08-12 (admin 联调修复): 原实现 `.catch( => null)` 吞掉取消后无条件执行批准
 // —— 用户点"取消"也会批准。改为 catch 后 return（仅在确认后执行）。
  try {
    await ElMessageBox.confirm(
      `确认批量批准 ${selection.value.length} 项？批准后将出现在公开图谱中。`,
      '批量批准',
      { type: 'warning', confirmButtonText: '确认批准', cancelButtonText: '取消' },
    )
  } catch {
    return  // 用户取消 — 不执行批准
  }
  await callBatch('approve')
}

async function batchReject() {
  if (selection.value.length === 0) return
  const { value: reason } = await ElMessageBox.prompt(
    `将拒绝 ${selection.value.length} 项，请输入拒绝原因（会写入数据库）：`,
    '批量拒绝',
    { confirmButtonText: '确认拒绝', cancelButtonText: '取消', inputPlaceholder: '例如：与项目无关 / 数据质量差' },
  ).catch(() => ({ value: null }))
 // 2026-08-12: 用 null 区分"用户取消"与"确认但空原因"；取消不执行，空原因也拦截（拒绝原因必填）
  if (reason === null || !reason?.trim()) return
  await callBatch('reject', reason)
}

// 2026-08-21: 全选当前筛选（一键审核全部待审项）
// 修复1: 用 el-table toggleAllSelection() 触发 UI 勾选（此前直接赋值 selection
// 数组不触发表格复选框，用户看到"已选 200 项"但复选框不亮）
// 修复2: 文案区分「当前已加载 N 项」—— 后端 limit=200 只拉前 200 条，
// 全部待审可能更多（743 岗位 + 524 技能），单独提供「全选全部待审」按钮
const tableRef = ref<{ toggleAllSelection: () => void; clearSelection: () => void } | null>(null)

function selectAllFiltered() {
  // 全选当前表格可见页（20 条）—— toggleAllSelection 只作用于当前渲染数据
  tableRef.value?.toggleAllSelection()
}

// 全选全部待审（不分页拉全部 ID，走批量审核端点）
const selectingAll = ref(false)
async function selectAllPending() {
  if (selectingAll.value) return
  selectingAll.value = true
  try {
    const limit = 2000
    const [posRes, skillRes] = await Promise.all([
      request.get('/admin/review-items', { params: { entity_type: 'position', status: 'pending_review', limit } }),
      request.get('/admin/review-items', { params: { entity_type: 'skill', status: 'pending_review', limit } }),
    ])
    const posItems = (posRes as { items?: ReviewItem[] }).items ?? []
    const skillItems = (skillRes as { items?: ReviewItem[] }).items ?? []
    const all: ReviewItem[] = [...posItems, ...skillItems]
    if (all.length === 0) {
      ElMessage.info('没有待审核内容')
      return
    }
    // 直接设置 selection（含未渲染项）—— 批量端点按 ID 审核，无需表格勾选态
    selection.value = all
    ElMessage.success(`已全选全部待审 ${all.length} 项（岗位 ${posItems.length} + 技能 ${skillItems.length}）`)
  } catch (e) {
    ElMessage.error('获取全部待审失败: ' + (e instanceof Error ? e.message : '未知错误'))
  } finally {
    selectingAll.value = false
  }
}

const filteredItems = computed<ReviewItem[]>(() => {
  let list = reviewStore.items
  if (entityTypeFilter.value) {
    list = list.filter((i) => i.entity_type === entityTypeFilter.value)
  }
  if (statusFilter.value) {
    list = list.filter((i) => i.review_status === statusFilter.value)
  }
  const q = searchKeyword.value.trim().toLowerCase()
  if (q) {
    list = list.filter((i) => i.name.toLowerCase().includes(q))
  }
  return list
})

const pagedItems = computed<ReviewItem[]>(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredItems.value.slice(start, start + pageSize.value)
})

const totalFiltered = computed(() => filteredItems.value.length)

const STATUS_OPTIONS: { value: '' | ReviewStatus; label: string }[] = [
  { value: '', label: ALL_OPTION },
  { value: 'pending_review', label: POSITION_REVIEW_STATUS_LABELS.pending_review },
  { value: 'approved', label: POSITION_REVIEW_STATUS_LABELS.approved },
  { value: 'rejected', label: POSITION_REVIEW_STATUS_LABELS.rejected },
  { value: 'draft', label: POSITION_REVIEW_STATUS_LABELS.draft },
]

const TYPE_OPTIONS: { value: '' | ReviewEntityType; label: string }[] = [
  { value: '', label: '全部类型' },
  { value: 'position', label: '岗位' },
  { value: 'skill', label: '技能' },
]

const statusTagType = (status: ReviewStatus) => {
  switch (status) {
    case 'approved': return 'success'
    case 'pending_review': return 'warning'
    case 'rejected': return 'danger'
    case 'draft': return 'info'
  }
}

const statusLabel = (status: ReviewStatus) => POSITION_REVIEW_STATUS_LABELS[status] ?? status

async function refresh() {
  await reviewStore.fetchItems(
    entityTypeFilter.value || undefined,
    statusFilter.value || undefined,
    200,
  )
  await reviewStore.fetchStats()
}

onMounted(refresh)

// Re-fetch when filters change
watch([entityTypeFilter, statusFilter], () => {
  currentPage.value = 1
  refresh()
})

async function handleApprove(item: ReviewItem) {
  try {
    const { value: reason } = await ElMessageBox.prompt(
      '批准原因 (可选)',
      `批准「${item.name}」`,
      { confirmButtonText: '确认批准', cancelButtonText: '取消', inputPlaceholder: '可选填写备注' },
    ).catch(() => ({ value: null }))
    if (reason === null) return  // user cancelled
    await reviewStore.approve(item.entity_type, item.entity_id, reason || undefined)
    ElMessage.success('已批准')
    reviewStore.removeLocal(item.entity_id)
    await reviewStore.fetchStats()
  } catch (e) {
    ElMessage.error('批准失败: ' + (e instanceof Error ? e.message : '未知错误'))
  }
}

async function handleReject(item: ReviewItem) {
  try {
    const { value: reason } = await ElMessageBox.prompt(
      '拒绝原因 (必填)',
      `拒绝「${item.name}」`,
      {
        confirmButtonText: '确认拒绝',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputValidator: (val) => (val && val.trim() ? true : '请填写拒绝原因'),
      },
    )
    if (!reason || !reason.trim()) return
    await reviewStore.reject(item.entity_type, item.entity_id, reason.trim())
    ElMessage.success('已拒绝')
    reviewStore.removeLocal(item.entity_id)
    await reviewStore.fetchStats()
  } catch (e) {
 // ElMessageBox.prompt throws when cancelled — suppress that.
    if (e instanceof Error && !e.message.includes('cancel')) {
      ElMessage.error('拒绝失败: ' + e.message)
    }
  }
}

async function handleUnpublish(item: ReviewItem) {
  try {
    const { value: reason } = await ElMessageBox.prompt(
      '下架原因 (必填)',
      `下架「${item.name}」`,
      {
        confirmButtonText: '确认下架',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputValidator: (val) => (val && val.trim() ? true : '请填写下架原因'),
      },
    )
    if (!reason || !reason.trim()) return
    await reviewStore.unpublish(item.entity_type, item.entity_id, reason.trim())
    ElMessage.success('已下架')
    reviewStore.removeLocal(item.entity_id)
    await refresh()
  } catch (e) {
    if (e instanceof Error && !e.message.includes('cancel')) {
      ElMessage.error('下架失败: ' + e.message)
    }
  }
}

function formatDate(s: string | null) {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleString()
  } catch {
    return s
  }
}

// ── 提交来源语义化: system:* 内部标识 → 用户友好中文标签（集中化自 labels.ts）──
const SOURCE_LABELS = REVIEW_SOURCE_LABELS
function sourceLabel(createdBy: string | null): { label: string; isSystem: boolean } {
  if (!createdBy) return { label: '未知来源', isSystem: true }
  if (SOURCE_LABELS[createdBy]) return { label: SOURCE_LABELS[createdBy], isSystem: true }
  if (createdBy.startsWith('system:') || createdBy.includes(':')) {
    return { label: createdBy, isSystem: true }
  }
  return { label: `管理员（${createdBy}）`, isSystem: false }
}

// ── 中文名调整手工校准): 复用内容审核模块，审核时直接修正 name_cn ──
const nameCnEditor = ref<ReviewItem | null>(null)
const nameCnValue = ref('')
const nameCnSaving = ref(false)

function openNameCnEditor(item: ReviewItem) {
  nameCnEditor.value = item
  nameCnValue.value = item.name_cn ?? ''
}

async function saveNameCn() {
  if (!nameCnEditor.value) return
  const name = (nameCnValue.value ?? '').trim()
  if (!name) {
    ElMessage.warning('中文名不能为空')
    return
  }
  nameCnSaving.value = true
  try {
    const item = nameCnEditor.value
    await request.patch(
      `/admin/review/${item.entity_type}/${item.entity_id}/name-cn`,
      { name_cn: name },
    )
    ElMessage.success(`已更新「${item.name}」中文名: ${name}`)
    nameCnEditor.value = null
    await refresh()
  } catch (e) {
    ElMessage.error(`更新中文名失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    nameCnSaving.value = false
  }
}

// ── A3 人工优化：编辑岗位定义五要素（行业场景/核心职责/加分技能/简述）──
const defEditor = ref<ReviewItem | null>(null)
const defForm = reactive({
  industry_scenario: '',
  core_responsibilities: [] as string[],
  bonus_skills: [] as string[],
  summary: '',
})
const defSaving = ref(false)
const defSkillInput = ref('')
const defBonusInput = ref('')

function openDefEditor(item: ReviewItem) {
  defEditor.value = item
  defForm.industry_scenario = ''
  defForm.core_responsibilities = []
  defForm.bonus_skills = []
  defForm.summary = ''
  defSkillInput.value = ''
  defBonusInput.value = ''
}

function addDefSkill() {
  const v = defSkillInput.value.trim()
  if (v && !defForm.core_responsibilities.includes(v)) {
    defForm.core_responsibilities.push(v)
  }
  defSkillInput.value = ''
}

function addDefBonus() {
  const v = defBonusInput.value.trim()
  if (v && !defForm.bonus_skills.includes(v)) {
    defForm.bonus_skills.push(v)
  }
  defBonusInput.value = ''
}

async function saveDefEditor() {
  if (!defEditor.value) return
  const payload: Record<string, unknown> = {}
  if (defForm.industry_scenario.trim()) {
    payload.industry_scenario = defForm.industry_scenario.trim()
  }
  if (defForm.core_responsibilities.length > 0) {
    payload.core_responsibilities = defForm.core_responsibilities
  }
  if (defForm.bonus_skills.length > 0) {
    payload.bonus_skills = defForm.bonus_skills
  }
  if (defForm.summary.trim()) {
    payload.summary = defForm.summary.trim()
  }
  if (Object.keys(payload).length === 0) {
    ElMessage.warning('请至少填写一项内容')
    return
  }
  defSaving.value = true
  try {
    const item = defEditor.value
    await request.patch(
      `/admin/review/${item.entity_type}/${item.entity_id}/definition`,
      payload,
    )
    ElMessage.success(`已更新「${item.name}」岗位定义`)
    defEditor.value = null
    await refresh()
  } catch (e) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail ?? `更新岗位定义失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    defSaving.value = false
  }
}
</script>

<template>
  <div class="content-review-panel">
    <!-- Stats row -->
    <div class="stats-row">
      <el-tooltip
        content="审核通过、对外可见、可被检索的岗位数量。"
        placement="top"
      >
        <div class="stat-item">
          <span class="stat-value">{{ reviewStore.stats.position_approved ?? 0 }}</span>
          <span class="stat-label">已发布岗位</span>
        </div>
      </el-tooltip>
      <el-tooltip
        content="已抽取、尚未完成审核的岗位数量。"
        placement="top"
      >
        <div class="stat-item">
          <span class="stat-value warn">{{ reviewStore.stats.position_pending_review ?? 0 }}</span>
          <span class="stat-label">待审岗位</span>
        </div>
      </el-tooltip>
      <el-tooltip
        content="审核未通过、未对外发布的岗位数量。"
        placement="top"
      >
        <div class="stat-item">
          <span class="stat-value danger">{{ reviewStore.stats.position_rejected ?? 0 }}</span>
          <span class="stat-label">已拒岗位</span>
        </div>
      </el-tooltip>
      <el-tooltip
        content="审核通过、可对外引用的技能数量。"
        placement="top"
      >
        <div class="stat-item">
          <span class="stat-value">{{ reviewStore.stats.skill_approved ?? 0 }}</span>
          <span class="stat-label">已发布技能</span>
        </div>
      </el-tooltip>
      <el-tooltip
        content="已抽取、尚未完成审核的技能数量。"
        placement="top"
      >
        <div class="stat-item">
          <span class="stat-value warn">{{ reviewStore.stats.skill_pending_review ?? 0 }}</span>
          <span class="stat-label">待审技能</span>
        </div>
      </el-tooltip>
      <el-button
        :icon="RefreshRight"
        plain
        size="small"
        class="refresh-btn"
        @click="refresh"
      >
        刷新
      </el-button>
    </div>

    <!-- Filters -->
    <div class="filter-row">
      <el-input
        v-model="searchKeyword"
        placeholder="按名称搜索..."
        clearable
        size="default"
        class="search-input"
      />
      <el-select
        v-model="entityTypeFilter"
        size="default"
        class="type-select"
      >
        <el-option
          v-for="opt in TYPE_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <el-select
        v-model="statusFilter"
        size="default"
        class="status-select"
      >
        <el-option
          v-for="opt in STATUS_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
    </div>

    <!-- 2026-08-21: 全选当前筛选（一键审核全部待审项） -->
    <div
      v-if="filteredItems.length > 0 && selection.length === 0"
      class="batch-toolbar select-all-bar"
    >
      <!-- 2026-08-21: 语义修正 —— 区分「已加载」与「全部待审」真实总数 -->
      <span class="batch-count">已加载 {{ filteredItems.length }} / 全部待审 {{ reviewStore.filterTotal || filteredItems.length }} 项</span>
      <el-button
        size="small"
        plain
        :disabled="reviewStore.loading"
        @click="selectAllFiltered"
      >
        全选当前页
      </el-button>
      <el-button
        size="small"
        type="primary"
        plain
        :loading="selectingAll"
        :disabled="reviewStore.loading"
        @click="selectAllPending"
      >
        全选全部待审
      </el-button>
    </div>

    <!-- 批量操作工具栏 -->
    <div
      v-if="selection.length > 0"
      class="batch-toolbar"
    >
      <span class="batch-count">已选 {{ selection.length }} 项</span>
      <el-button
        size="small"
        type="success"
        :disabled="reviewStore.loading"
        @click="batchApprove"
      >
        批量批准
      </el-button>
      <el-button
        size="small"
        type="danger"
        :disabled="reviewStore.loading"
        @click="batchReject"
      >
        批量拒绝
      </el-button>
      <el-button
        size="small"
        text
        @click="selection = []"
      >
        清除选择
      </el-button>
    </div>

    <!-- Table -->
    <el-table
      ref="tableRef"
      v-loading="reviewStore.loading"
      :data="pagedItems"
      stripe
      size="default"
      row-key="entity_id"
      empty-text="暂无审核项"
      class="review-table"
      @selection-change="(rows: any[]) => selection = rows"
    >
      <el-table-column
        type="selection"
        width="48"
      />
      <el-table-column
        label="类型"
        width="80"
      >
        <template #default="{ row }">
          <el-tag
            :type="row.entity_type === 'position' ? 'primary' : 'success'"
            size="small"
            effect="plain"
          >
            {{ row.entity_type === 'position' ? '岗位' : '技能' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="名称"
        min-width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <!--: 中文名优先展示（name_cn || name），改中文名后即时生效 -->
          <span class="entity-name">{{ row.name_cn || row.name }}</span>
          <el-tag
            v-if="row.name_cn && row.name_cn !== row.name"
            size="small"
            type="info"
            effect="plain"
            class="origin-name-tag"
          >
            {{ row.name }}
          </el-tag>
          <span
            v-if="row.industry"
            class="industry-tag"
          >{{ row.industry }}</span>
        </template>
      </el-table-column>
      <el-table-column
        label="状态"
        width="100"
      >
        <template #default="{ row }">
          <el-tag
            :type="statusTagType(row.review_status)"
            size="small"
            effect="plain"
          >
            {{ statusLabel(row.review_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="提交来源"
        min-width="130"
        show-overflow-tooltip
      >
        <!-- 提交来源语义化: system:* 内部标识 → 用户友好中文标签（流水线抽取/JD抽取/历史数据等） -->
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="sourceLabel(row.created_by).isSystem ? 'info' : 'primary'"
            effect="plain"
          >
            {{ sourceLabel(row.created_by).label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="审核人"
        min-width="120"
        show-overflow-tooltip
      >
        <!-- "审核人" is empty by design for pending items; will be
             populated when the row is approved/rejected. -->
        <template #default="{ row }">
          <span
            v-if="row.reviewed_by"
            class="reviewer"
          >{{ row.reviewed_by }}</span>
          <span
            v-else
            class="muted"
          >未审核</span>
        </template>
      </el-table-column>
      <el-table-column
        label="提交时间"
        min-width="170"
      >
        <!-- E2 fix: submitted_at is the time the item entered pending_review.
             Fall back to created_at so the column never shows "—". -->
        <template #default="{ row }">
          {{ formatDate(row.submitted_at ?? row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column
        label="拒绝原因"
        min-width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <span
            v-if="row.review_status === 'rejected' && row.rejection_reason"
            class="rejection-reason"
          >
            {{ row.rejection_reason }}
          </span>
          <span
            v-else
            class="muted"
          >—</span>
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        width="360"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button
            size="small"
            plain
            :icon="EditPen"
            @click="openNameCnEditor(row)"
          >
            改中文名
          </el-button>
          <el-button
            v-if="row.entity_type === 'position'"
            size="small"
            plain
            type="primary"
            :icon="EditPen"
            @click="openDefEditor(row)"
          >
            编辑定义
          </el-button>
          <el-button
            v-if="row.review_status === 'pending_review'"
            type="success"
            size="small"
            :icon="Check"
            @click="handleApprove(row)"
          >
            批准
          </el-button>
          <el-button
            v-if="row.review_status === 'pending_review'"
            type="danger"
            size="small"
            :icon="Close"
            plain
            @click="handleReject(row)"
          >
            拒绝
          </el-button>
          <el-button
            v-if="row.review_status === 'approved'"
            type="warning"
            size="small"
            plain
            @click="handleUnpublish(row)"
          >
            下架
          </el-button>
          <span
            v-if="row.review_status === 'rejected'"
            class="muted"
          >已拒绝</span>
          <span
            v-if="row.review_status === 'draft'"
            class="muted"
          >草稿</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- BUG-7 fix: always render pagination (was hidden when totalFiltered ≤ pageSize,
         making single-page queues feel dead-end). Disabled state when total is small. -->
    <div class="pagination-row">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="Math.min(reviewStore.filterTotal ?? Infinity, totalFiltered)"
        :disabled="totalFiltered <= pageSize"
        layout="prev, pager, next, total"
      />
    </div>

    <!-- 中文名调整弹窗 ( 手工校准): 审核队列中直接修正 name_cn -->
    <el-dialog
      :model-value="nameCnEditor !== null"
      :title="nameCnEditor ? `调整中文名 — ${nameCnEditor.entity_type === 'position' ? '岗位' : '技能'}「${nameCnEditor.name}」` : ''"
      width="460px"
      append-to-body
      destroy-on-close
      @update:model-value="(v: boolean) => { if (!v) nameCnEditor = null }"
    >
      <el-form
        v-if="nameCnEditor"
        label-position="top"
        @submit.prevent="saveNameCn"
      >
        <el-form-item label="原名（原文）">
          <el-input
            :model-value="nameCnEditor.name"
            disabled
          />
        </el-form-item>
        <el-form-item label="中文名（name_cn）">
          <el-input
            v-model="nameCnValue"
            placeholder="输入中文显示名，如：数据工程师"
            maxlength="255"
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="nameCnEditor = null">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="nameCnSaving"
          @click="saveNameCn"
        >
          保存中文名
        </el-button>
      </template>
    </el-dialog>

    <!-- A3 人工优化：岗位定义五要素编辑弹窗（行业场景/核心职责/加分技能/简述） -->
    <el-dialog
      :model-value="defEditor !== null"
      :title="defEditor ? `编辑岗位定义 — 「${defEditor.name}」` : ''"
      width="620px"
      append-to-body
      destroy-on-close
      @update:model-value="(v: boolean) => { if (!v) defEditor = null }"
    >
      <el-form
        v-if="defEditor"
        label-position="top"
      >
        <el-form-item label="典型行业应用场景">
          <el-input
            v-model="defForm.industry_scenario"
            type="textarea"
            :rows="2"
            placeholder="如：自动驾驶 · 车路协同；金融风控 · 实时决策"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="核心职责（逐条添加）">
          <div class="def-tag-row">
            <el-tag
              v-for="(r, i) in defForm.core_responsibilities"
              :key="`cr-${i}`"
              closable
              @close="defForm.core_responsibilities.splice(i, 1)"
            >
              {{ r }}
            </el-tag>
          </div>
          <div class="def-input-row">
            <el-input
              v-model="defSkillInput"
              placeholder="输入职责后回车添加，如：负责系统架构设计"
              @keyup.enter="addDefSkill"
            />
            <el-button @click="addDefSkill">
              添加
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="加分技能（逐条添加）">
          <div class="def-tag-row">
            <el-tag
              v-for="(b, i) in defForm.bonus_skills"
              :key="`bn-${i}`"
              type="warning"
              closable
              @close="defForm.bonus_skills.splice(i, 1)"
            >
              {{ b }}
            </el-tag>
          </div>
          <div class="def-input-row">
            <el-input
              v-model="defBonusInput"
              placeholder="输入技能后回车添加，如：Kubernetes"
              @keyup.enter="addDefBonus"
            />
            <el-button @click="addDefBonus">
              添加
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="岗位简述">
          <el-input
            v-model="defForm.summary"
            type="textarea"
            :rows="2"
            placeholder="一句话概述该岗位的定位与价值"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="defEditor = null">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="defSaving"
          @click="saveDefEditor"
        >
          保存定义
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.content-review-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.stats-row {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-3) var(--space-4);
  background: color-mix(in srgb, var(--primary) 3%, var(--card));
  border-radius: var(--radius-lg);
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 80px;
}

.stat-value {
  font-size: var(--font-size-2xl);
  font-weight: 800;
  color: var(--foreground);
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.stat-value.warn { color: var(--warning); }
.stat-value.danger { color: var(--destructive); }

.stat-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  margin-top: 2px;
}

.refresh-btn { margin-left: auto; }

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-3);
  background: color-mix(in srgb, var(--primary) 5%, var(--card));
  border: 1px solid color-mix(in srgb, var(--primary) 30%, transparent);
  border-radius: var(--radius-lg);
}
.batch-count {
  font-weight: 600;
  color: var(--primary);
  margin-right: var(--space-2);
}

.filter-row {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.search-input { flex: 1; min-width: 200px; }
.type-select { width: 130px; }
.status-select { width: 130px; }

.review-table { border-radius: var(--radius-lg); overflow: hidden; }

.entity-name {
  font-weight: 500;
  color: var(--foreground);
  margin-right: var(--space-2);
}

.origin-name-tag {
  margin-right: var(--space-2);
}

.industry-tag {
  display: inline-block;
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  padding: 1px 6px;
  background: var(--muted);
  border-radius: var(--radius-sm);
}

.rejection-reason {
  color: var(--destructive);
  font-size: var(--font-size-xs);
  line-height: 1.4;
}

.muted {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
}

.pagination-row {
  display: flex;
  justify-content: center;
  padding: var(--space-3) 0;
}

.def-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  min-height: 24px;
}

.def-input-row {
  display: flex;
  gap: var(--space-2);
  width: 100%;
}
</style>
