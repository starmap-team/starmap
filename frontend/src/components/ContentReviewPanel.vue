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
import { onMounted, ref, computed, watch } from 'vue'
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

async function batchApprove() {
  if (selection.value.length === 0) return
  // 2026-08-12 (admin 联调修复): 原实现 `.catch(() => null)` 吞掉取消后无条件执行批准
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
  let ok = 0; let fail = 0
  for (const item of selection.value) {
    try {
      await reviewStore.approve(item.entity_type as ReviewEntityType, item.entity_id)
      ok++
    } catch { fail++ }
  }
  selection.value = []
  await reviewStore.fetchItems()
  await reviewStore.fetchStats()
  ElMessage[fail === 0 ? 'success' : 'warning'](`批准完成: ${ok} 成功, ${fail} 失败`)
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
  let ok = 0; let fail = 0
  for (const item of selection.value) {
    try {
      await reviewStore.reject(item.entity_type as ReviewEntityType, item.entity_id, reason)
      ok++
    } catch { fail++ }
  }
  selection.value = []
  await reviewStore.fetchItems()
  await reviewStore.fetchStats()
  ElMessage[fail === 0 ? 'success' : 'warning'](`拒绝完成: ${ok} 成功, ${fail} 失败`)
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

// IndustryClassifier (2026-08-17): admin 手动重新分类 industry。
// 多层防御第三层 — 当 LLM 抽取 / backfill / alias 字典把某岗位归到错误
// canonical 桶时，运营可在审核面板一键修正。端点：
// POST /api/v1/admin/positions/{position_id}/reclassify-industry
const reclassifyDialog = ref<{ open: boolean; item: ReviewItem | null }>({
  open: false,
  item: null,
})
const reclassifyIndustry = ref('')
const reclassifyReason = ref('')
const reclassifyLoading = ref(false)

async function openReclassifyDialog(item: ReviewItem) {
  if (item.entity_type !== 'position') {
    ElMessage.warning('仅岗位支持行业重新分类（技能无需行业字段）')
    return
  }
  reclassifyDialog.value = { open: true, item }
  reclassifyIndustry.value = item.industry || ''
  reclassifyReason.value = ''
}

async function submitReclassify() {
  const item = reclassifyDialog.value.item
  if (!item) return
  if (!reclassifyIndustry.value.trim()) {
    ElMessage.warning('请选择新的行业')
    return
  }
  if (reclassifyReason.value.trim().length < 5) {
    ElMessage.warning('请填写至少 5 字的原因')
    return
  }
  reclassifyLoading.value = true
  try {
    await request.post(
      `/api/v1/admin/positions/${item.entity_id}/reclassify-industry`,
      {
        industry: reclassifyIndustry.value.trim(),
        reason: reclassifyReason.value.trim(),
      },
    )
    ElMessage.success('行业重新分类已写入')
    reclassifyDialog.value.open = false
    await refresh()
  } catch (e) {
    const detail =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail ? `重新分类失败: ${detail}` : '重新分类失败')
  } finally {
    reclassifyLoading.value = false
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

// ── 中文名调整 (D8i/手工校准): 复用内容审核模块，审核时直接修正 name_cn ──
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
</script>

<template>
  <div class="content-review-panel">
    <!-- Stats row -->
    <div class="stats-row">
      <el-tooltip
        content="PostgreSQL position_records 表中 review_status='approved' 的岗位（用户可见、可检索）。"
        placement="top"
      >
        <div class="stat-item">
          <span class="stat-value">{{ reviewStore.stats.position_approved ?? 0 }}</span>
          <span class="stat-label">已发布岗位</span>
        </div>
      </el-tooltip>
      <el-tooltip
        content="PostgreSQL position_records 表中 review_status='pending_review' 的岗位（需人工审核才能发布）。"
        placement="top"
      >
        <div class="stat-item">
          <span class="stat-value warn">{{ reviewStore.stats.position_pending_review ?? 0 }}</span>
          <span class="stat-label">待审岗位</span>
        </div>
      </el-tooltip>
      <el-tooltip
        content="PostgreSQL position_records 表中 review_status='rejected' 的岗位。"
        placement="top"
      >
        <div class="stat-item">
          <span class="stat-value danger">{{ reviewStore.stats.position_rejected ?? 0 }}</span>
          <span class="stat-label">已拒岗位</span>
        </div>
      </el-tooltip>
      <el-tooltip
        content="PostgreSQL skill_records 表中 review_status='approved' 的技能。"
        placement="top"
      >
        <div class="stat-item">
          <span class="stat-value">{{ reviewStore.stats.skill_approved ?? 0 }}</span>
          <span class="stat-label">已发布技能</span>
        </div>
      </el-tooltip>
      <el-tooltip
        content="PostgreSQL skill_records 表中 review_status='pending_review' 的技能。"
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
      v-loading="reviewStore.loading"
      :data="pagedItems"
      stripe
      size="default"
      empty-text="暂无审核项"
      class="review-table"
      @selection-change="(rows: ReviewItem[]) => selection = rows"
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
          <!-- D8i/D8j: 中文名优先展示（name_cn || name），改中文名后即时生效 -->
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
          <el-tag
            :type="row.industry ? 'info' : 'warning'"
            :effect="row.industry ? 'light' : 'plain'"
            size="small"
            class="industry-tag"
            :title="row.industry ? `行业: ${row.industry}` : '该岗位尚未标注行业'"
          >{{ row.industry || '未分类' }}</el-tag>
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
        width="280"
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
          <el-button
            v-if="row.entity_type === 'position' && row.review_status === 'approved'"
            type="primary"
            size="small"
            plain
            :icon="RefreshRight"
            title="Phase 3: Admin 手动重新分类 industry（多层防御 IndustryClassifier 第三层）"
            @click="openReclassifyDialog(row)"
          >
            重分类行业
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
        :total="totalFiltered"
        :disabled="totalFiltered <= pageSize"
        layout="prev, pager, next, total"
      />
    </div>

    <!-- 中文名调整弹窗 (D8i/手工校准): 审核队列中直接修正 name_cn -->
    <el-dialog
      :model-value="nameCnEditor !== null"
      :title="nameCnEditor ? `调整中文名 — ${nameCnEditor.entity_type === 'position' ? '岗位' : '技能'}「${nameCnEditor.name}」` : ''"
      width="460px"
      append-to-body
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

    <!-- Phase 3: Admin reclassify-industry 对话框 (多层防御第三层) -->
    <el-dialog
      v-model="reclassifyDialog.open"
      title="重新分类行业"
      width="520px"
      :close-on-click-modal="false"
      append-to-body
    >
      <p class="reclassify-hint">
        当前行业：
        <strong>{{ reclassifyDialog.item?.industry || '未分类' }}</strong>
        （岗位：{{ reclassifyDialog.item?.name_cn || reclassifyDialog.item?.name }}）
      </p>
      <el-form label-width="80px">
        <el-form-item label="新行业" required>
          <el-input
            v-model="reclassifyIndustry"
            placeholder="输入 industry_taxonomy.yaml canonical 桶（如：互联网/IT / 金融科技 / 销售/营销）"
            clearable
          />
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input
            v-model="reclassifyReason"
            type="textarea"
            :rows="3"
            placeholder="至少 5 字，说明重新分类原因（写入 ReviewAuditLog）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reclassifyDialog.open = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="reclassifyLoading"
          @click="submitReclassify"
        >
          提交重分类
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
  margin-left: var(--space-2);
}

.reclassify-hint {
  margin-bottom: var(--space-4);
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
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
</style>
