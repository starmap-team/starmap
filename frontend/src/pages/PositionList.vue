<script setup lang="ts">
/**
 * 岗位列表页 — 从后端 /positions 获取岗位数据
 *
 * review-workflow awareness —
 * - Default view shows only approved positions (public).
 * - Admin can switch to "All" or specific status (pending_review, etc.)
 *   to see positions awaiting review.
 * - Each card displays a status badge so the workflow state is visible
 *   at a glance.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import MainLayout from '@/layouts/MainLayout.vue'
import { useJdStore } from '@/stores/jd'
import { useUserStore } from '@/stores/user'
import { ALL_OPTION, POSITION_REVIEW_STATUS_LABELS } from '@/constants/labels'
import { freshnessOf } from '@/utils/freshness'

const jdStore = useJdStore()
const userStore = useUserStore()

const router = useRouter()
const isAdmin = computed(() => userStore.isAdmin)

interface PositionRow {
  id: string
  name: string
  name_cn?: string
  industry: string
  review_status?: 'draft' | 'pending_review' | 'approved' | 'rejected'
  reviewed_by?: string | null
  rejection_reason?: string | null
  // PLAN-006④: 岗位入库时间, 用于卡片"数据时效"指示; null = 演示/无采集
  discovered_at?: string | null
}

const positions = ref<PositionRow[]>([])
const loading = ref(false)
const searchQuery = ref('')
const selectedIndustry = ref('')
const total = ref(0)
const page = ref(1)
const pageSize = ref(24)

// status filter.
// Default to 'all' so the list is never empty on first load.
// Admin and regular users both see all positions; status badges distinguish visibility.
const statusFilter = ref<'approved' | 'pending_review' | 'rejected' | 'all'>('all')

// US-3: 行业列表从后端 /positions/industries 获取全量，而非仅当前页
const industries = ref<string[]>([])

async function loadIndustries() {
  try {
    industries.value = await jdStore.fetchIndustries()
  } catch {
    // 静默降级：API 不可用时从当前页提取
    const set = new Set(positions.value.map(p => p.industry).filter(Boolean))
    industries.value = Array.from(set).sort()
  }
}

// 后端已统一处理搜索/行业筛选/分页，前端直接展示即可
const filteredPositions = computed(() => positions.value)

const showAdminFilters = computed(() => isAdmin.value)

const statusOptions: { value: typeof statusFilter.value; label: string }[] = [
  { value: 'approved', label: POSITION_REVIEW_STATUS_LABELS.approved },
  { value: 'pending_review', label: POSITION_REVIEW_STATUS_LABELS.pending_review },
  { value: 'rejected', label: POSITION_REVIEW_STATUS_LABELS.rejected },
  { value: 'all', label: ALL_OPTION },
]

function statusBadgeType(status: PositionRow['review_status'] | undefined) {
  switch (status) {
    case 'approved':
      return 'success'
    case 'pending_review':
      return 'warning'
    case 'rejected':
      return 'danger'
    case 'draft':
      return 'info'
    default:
      return 'info'
  }
}

function statusLabel(status: PositionRow['review_status'] | undefined) {
  if (!status) return '—'
  return POSITION_REVIEW_STATUS_LABELS[status] ?? status
}

  async function fetchPositions() {
    loading.value = true
    try {
      const params: {
        page: number
        page_size: number
        search?: string
        industry?: string
        status?: 'draft' | 'pending_review' | 'approved' | 'rejected' | 'all'
        include_all?: boolean
      } = {
        page: page.value,
        page_size: pageSize.value,
      }
      // fix: 传递搜索关键字和行业筛选到后端，确保分页与筛选协同
      const q = searchQuery.value.trim()
      if (q) params.search = q
      if (selectedIndustry.value) params.industry = selectedIndustry.value
      // 审核状态过滤：公开契约 = 仅 approved；include_all 仅 admin 可用
      // 非 admin 不传 include_all/status → 后端默认 approved（与全景图谱“已发布”口径一致）
      if (isAdmin.value) {
        if (statusFilter.value === 'all') {
          params.include_all = true
        } else if (statusFilter.value !== 'approved') {
          params.status = statusFilter.value
          params.include_all = true
        }
      }
      const data = await jdStore.fetchPositions(params)
      positions.value = data.items.map((p) => ({
        id: p.position_id,
        name: p.name,
        name_cn: p.name_cn || '',
        industry: p.industry,
        review_status: p.review_status ?? 'approved',
        reviewed_by: p.reviewed_by ?? null,
        rejection_reason: p.rejection_reason ?? null,
        discovered_at: p.discovered_at ?? null,
      }))
      total.value = data.total
    } catch (e) {
      if (import.meta.env.DEV) console.error('[PositionList] Failed to fetch:', e)
      ElMessage.error('岗位列表加载失败，请确认后端服务已启动')
    } finally {
      loading.value = false
    }
  }

function onPageChange(newPage: number) {
  page.value = newPage
  fetchPositions()
}

function onStatusFilterChange() {
  page.value = 1
  fetchPositions()
}

function goDetail(id: string) {
  // 按 UUID 跳转：名称可能含 `/` 等路径不安全字符（如 "UI/UX设计师"），
  // 用名称做路径段会让详情路由 404；UUID 无特殊字符，且后端 get_position 已支持 UUID。
  router.push(`/position/${id}`)
}

// 名称是否含中文；用于在卡片上诚实标注“英文原文”，避免英文岗位被误读为“中文展示缺失”
function hasCJK(s: string | undefined | null): boolean {
  return /[㐀-鿿]/.test(s ?? '')
}

function goExtract() {
  router.push('/extract')
}

// ── 搜索/筛选变更时重新查询后端（修复: 此前缺少 watcher 导致仅客户端过滤当前页） ──
let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchPositions()
  }, 300)
})
watch(selectedIndustry, () => {
  page.value = 1
  fetchPositions()
})

onMounted(() => {
  fetchPositions()
  loadIndustries()
})
</script>

<template>
  <MainLayout>
    <div class="position-list-page animate-fade-in">
      <div class="page-header">
        <h2>岗位列表</h2>
        <p class="subtitle">
          选择岗位查看能力雷达图与技能详情
        </p>
      </div>

      <el-input
        v-model="searchQuery"
        placeholder="搜索岗位名称或行业..."
        clearable
        size="large"
        class="search-input-wrapper"
        :prefix-icon="Search"
      />

      <!-- Admin: review-status filter chips -->
      <div
        v-if="showAdminFilters"
        class="status-filter-row"
      >
        <span class="filter-label">审核状态:</span>
        <el-tag
          v-for="opt in statusOptions"
          :key="opt.value"
          :type="statusFilter === opt.value ? 'primary' : 'info'"
          :effect="statusFilter === opt.value ? 'dark' : 'plain'"
          class="clickable-tag"
          role="button"
          tabindex="0"
          @click="statusFilter = opt.value; onStatusFilterChange()"
        >
          {{ opt.label }}
        </el-tag>
      </div>

      <div class="industry-tags">
        <el-tag
          :type="selectedIndustry === '' ? 'primary' : 'info'"
          :effect="selectedIndustry === '' ? 'dark' : 'plain'"
          class="clickable-tag"
          role="button"
          tabindex="0"
          aria-label="筛选全部行业"
          @click="selectedIndustry = ''"
        >
          全部
        </el-tag>
        <el-tag
          v-for="ind in industries"
          :key="ind"
          :type="selectedIndustry === ind ? 'primary' : 'info'"
          :effect="selectedIndustry === ind ? 'dark' : 'plain'"
          class="clickable-tag"
          role="button"
          tabindex="0"
          :aria-label="`筛选行业: ${ind}`"
          @click="selectedIndustry = selectedIndustry === ind ? '' : ind"
        >
          {{ ind }}
        </el-tag>
      </div>
      <div class="result-count">
        共 {{ total }} 个岗位
      </div>

      <!-- 有数据时 -->
      <el-row
        v-if="filteredPositions.length || loading"
        v-loading="loading"
        :gutter="20"
      >
        <el-col
          v-for="pos in filteredPositions"
          :key="pos.id"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
        >
          <el-card
            class="position-card card-interactive"
            shadow="hover"
            @click="goDetail(pos.id)"
          >
            <div class="card-content">
              <h3>
                {{ pos.name_cn || pos.name }}
                <el-tag
                  v-if="!hasCJK(pos.name_cn) && !hasCJK(pos.name)"
                  size="small"
                  type="warning"
                  effect="plain"
                  class="lang-badge"
                  title="该岗位源自英文 JD，暂无中文名（非数据缺失）"
                >
                  英文原文
                </el-tag>
              </h3>
              <div class="card-meta">
                <!-- D-04: 行业 chip（M10 数据透明）。行业缺失时诚实标注「未分类」而非渲染空 chip -->
                <el-tag
                  size="small"
                  :type="pos.industry ? 'info' : 'warning'"
                  :effect="pos.industry ? 'light' : 'plain'"
                  class="industry-chip"
                  :title="pos.industry ? `行业: ${pos.industry}` : '该岗位尚未标注行业'"
                >
                  {{ pos.industry || '未分类' }}
                </el-tag>
                <!-- PLAN-006④: 数据时效指示 (演示数据 / 数据更新于 X / 较旧) -->
                <el-tag
                  size="small"
                  :type="freshnessOf(pos.discovered_at).type"
                  effect="plain"
                  class="freshness-tag"
                >
                  {{ freshnessOf(pos.discovered_at).label }}
                </el-tag>
                <el-tag
                  v-if="showAdminFilters"
                  :type="statusBadgeType(pos.review_status)"
                  size="small"
                  effect="plain"
                  class="status-badge"
                  :title="`审核人: ${pos.reviewed_by ?? '—'}`"
                >
                  {{ statusLabel(pos.review_status) }}
                </el-tag>
              </div>
              <p
                v-if="pos.review_status === 'rejected' && pos.rejection_reason"
                class="rejection-reason"
              >
                拒绝原因: {{ pos.rejection_reason }}
              </p>
            </div>
            <template #footer>
              <el-button
                type="primary"
                size="small"
                link
              >
                查看详情 →
              </el-button>
            </template>
          </el-card>
        </el-col>
      </el-row>

      <!-- 空状态引导 -->
      <div
        v-else
        class="empty-guide"
      >
        <div class="custom-empty">
          <div class="empty-icon-wrapper">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.2"
              stroke-linecap="round"
              stroke-linejoin="round"
            ><circle
              cx="11"
              cy="11"
              r="8"
            /><path d="m21 21-4.35-4.35" /></svg>
          </div>
          <p class="starmap-empty">
            未找到匹配的岗位
          </p>
          <p class="starmap-empty--hint">
            {{ statusFilter === 'pending_review'
              ? '没有待审核的岗位'
              : '尝试调整筛选条件或关键词' }}
          </p>
          <div
            v-if="statusFilter === 'pending_review'"
            class="empty-actions"
          >
            <p class="starmap-empty--hint">
              请到管理后台审核，或从 JD 中抽取新岗位
            </p>
            <el-button
              type="primary"
              :icon="Plus"
              @click="goExtract"
            >
              前往 JD 抽取
            </el-button>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div
        v-if="total > pageSize"
        class="pagination-wrapper"
      >
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="onPageChange"
        />
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.position-list-page {
  min-height: 400px;
}

.page-header {
  margin-bottom: var(--space-6);
}

.page-header h2 {
  font-size: var(--font-size-2xl);
  font-weight: 800;
  letter-spacing: var(--tracking-tight);
  margin: 0 0 4px;
  color: var(--foreground);
}

.subtitle {
  margin: 0;
  font-size: var(--font-size-base);
  color: var(--muted-foreground);
}

.position-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  margin-bottom: var(--space-5);
}

.position-card:hover {
  transform: translateY(-4px);
}

.card-content {
  text-align: center;
  padding: var(--space-3) 0;
}

.card-content h3 {
  margin: 0 0 8px;
  font-size: var(--font-size-lg);
  color: var(--foreground);
}

.card-meta {
  display: flex;
  justify-content: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: 4px;
}

.status-badge {
  font-weight: 500;
}
.industry-chip {
  font-weight: 500;
}
.lang-badge {
  vertical-align: middle;
  margin-left: 6px;
}

.rejection-reason {
  margin: 8px 0 0;
  padding: 6px 8px;
  background: color-mix(in srgb, var(--destructive) 8%, transparent);
  color: var(--destructive);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  line-height: 1.4;
  text-align: left;
}

/* 空状态引导 */
.empty-guide {
  display: flex;
  justify-content: center;
  padding: 60px 20px;
}

.empty-icon {
  font-size: 4rem;
  line-height: 1;
}

.empty-actions {
  text-align: center;
}

.empty-hint-text {
  color: var(--muted-foreground);
  font-size: var(--font-size-base);
  margin-bottom: var(--space-4);
  line-height: 1.6;
}

.search-input-wrapper { margin-bottom: var(--space-5); max-width: 400px; }
.status-filter-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.filter-label {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  font-weight: 500;
  margin-right: 4px;
}
.industry-tags { margin-bottom: var(--space-3); display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.clickable-tag { cursor: pointer; }
.result-count { margin-bottom: var(--space-4); color: var(--muted-foreground); font-size: var(--font-size-sm); }

/* ── Custom Empty State ── */
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) var(--space-6);
  text-align: center;
}
.empty-icon-wrapper {
  color: var(--muted-foreground);
  opacity: 0.4;
  margin-bottom: var(--space-4);
}
.empty-slot {
  margin-top: var(--space-4);
}
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: var(--space-6);
  padding: var(--space-4) 0;
}
</style>
