<script setup lang="ts">
/**
 * 审核队列面板 — 从 Admin.vue 提取的独立组件
 * 支持搜索、过滤、批量操作、单条审核
 */
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete } from '@element-plus/icons-vue'
import { useAdminStore } from '@/stores/admin'

const props = defineProps<{
  /** 是否显示操作栏（搜索 + 批量） */
  showActionBar?: boolean
}>()

const admin = useAdminStore()

// ── 搜索过滤 ──
const searchKeyword = ref('')
const typeFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(10)

const filteredAuditQueue = computed(() => {
  let list = admin.auditQueue
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    list = list.filter(i => i.name.toLowerCase().includes(kw))
  }
  if (typeFilter.value) {
    list = list.filter(i => i.type === typeFilter.value)
  }
  return list
})

const pagedAuditQueue = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredAuditQueue.value.slice(start, start + pageSize.value)
})

// ── 批量选择 ──
const selectedIds = ref<Set<number>>(new Set())
const isAllSelected = computed(() =>
  filteredAuditQueue.value.length > 0 &&
  filteredAuditQueue.value.every(i => selectedIds.value.has(i.id))
)

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(filteredAuditQueue.value.map(i => i.id))
  }
}

function toggleSelect(id: number) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

// ── 审核操作 ──
async function handleApprove(id: number) {
  await admin.approveAudit(id)
  selectedIds.value.delete(id)
  ElMessage.success('已批准')
}

async function handleReject(id: number) {
  await admin.rejectAudit(id)
  selectedIds.value.delete(id)
  ElMessage.warning('已拒绝')
}

async function handleBatchApprove() {
  if (!selectedIds.value.size) {
    ElMessage.warning('请先选择审核项')
    return
  }
  try {
    await ElMessageBox.confirm(`确认批量批准 ${selectedIds.value.size} 条？`, '批量操作', {
      confirmButtonText: '确认批准',
      type: 'warning',
    })
    for (const id of selectedIds.value) {
      await admin.approveAudit(id)
    }
    selectedIds.value = new Set()
    ElMessage.success('批量批准完成')
  } catch { /* 取消 */ }
}

async function handleBatchReject() {
  if (!selectedIds.value.size) {
    ElMessage.warning('请先选择审核项')
    return
  }
  try {
    await ElMessageBox.confirm(`确认批量拒绝 ${selectedIds.value.size} 条？`, '批量操作', {
      confirmButtonText: '确认拒绝',
      type: 'warning',
    })
    for (const id of selectedIds.value) {
      await admin.rejectAudit(id)
    }
    selectedIds.value = new Set()
    ElMessage.warning('批量拒绝完成')
  } catch { /* 取消 */ }
}
</script>

<template>
  <div class="review-queue-panel">
    <!-- 操作栏 -->
    <div
      v-if="props.showActionBar !== false"
      class="rq-action-bar"
    >
      <div class="rq-action-left">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索技能或岗位名..."
          :prefix-icon="Search"
          clearable
          class="rq-search-input"
          size="default"
        />
        <el-select
          v-model="typeFilter"
          placeholder="按类型过滤"
          clearable
          class="rq-type-filter"
          size="default"
        >
          <el-option
            label="全部"
            value=""
          />
          <el-option
            label="技能"
            value="skill"
          />
          <el-option
            label="岗位"
            value="position"
          />
        </el-select>
      </div>
      <div class="rq-action-right">
        <span
          v-if="selectedIds.size"
          class="rq-selected-count"
        >
          已选 {{ selectedIds.size }} 条
        </span>
        <el-button
          size="small"
          type="success"
          :disabled="!selectedIds.size"
          @click="handleBatchApprove"
        >
          批量通过
        </el-button>
        <el-button
          size="small"
          type="danger"
          :disabled="!selectedIds.size"
          @click="handleBatchReject"
        >
          批量拒绝
        </el-button>
      </div>
    </div>

    <!-- 表格 -->
    <el-table
      v-loading="admin.loading"
      :data="pagedAuditQueue"
      stripe
      size="default"
    >
      <el-table-column
        v-if="props.showActionBar !== false"
        width="50"
        align="center"
      >
        <template #header>
          <el-checkbox
            :model-value="isAllSelected"
            :indeterminate="selectedIds.size > 0 && !isAllSelected"
            @change="toggleSelectAll"
          />
        </template>
        <template #default="{ row }">
          <el-checkbox
            :model-value="selectedIds.has(row.id)"
            @change="toggleSelect(row.id)"
          />
        </template>
      </el-table-column>
      <el-table-column
        prop="id"
        label="ID"
        width="60"
        align="center"
      />
      <el-table-column
        prop="type"
        label="类型"
        width="85"
        align="center"
      >
        <template #default="{ row }">
          <el-tag
            :type="row.type === 'skill' ? 'success' : 'info'"
            size="small"
            effect="dark"
          >
            {{ row.type === 'skill' ? '技能' : '岗位' }}
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
        label="信任度"
        width="130"
        align="center"
      >
        <template #default="{ row }">
          <div style="display: flex; align-items: center; gap: 8px">
            <el-progress
              :percentage="row.trust"
              :stroke-width="6"
              :color="row.trust >= 70 ? '#67c23a' : row.trust >= 50 ? '#e6a23c' : '#f56c6c'"
              class="flex-1"
            />
            <span class="rq-trust-pct">{{ row.trust }}%</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        width="160"
        align="center"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button
            size="small"
            type="success"
            plain
            @click="handleApprove(row.id)"
          >
            通过
          </el-button>
          <el-button
            size="small"
            type="danger"
            plain
            @click="handleReject(row.id)"
          >
            拒绝
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 空状态 -->
    <div
      v-if="!filteredAuditQueue.length"
      class="rq-empty"
    >
      当前筛选条件下无审核项
    </div>

    <!-- 分页 -->
    <div
      v-if="filteredAuditQueue.length"
      class="rq-pagination"
    >
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="filteredAuditQueue.length"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        small
      />
    </div>
  </div>
</template>

<style scoped>
.review-queue-panel {
  width: 100%;
}

.rq-action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.rq-action-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.rq-action-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rq-search-input {
  width: 220px;
}

.rq-type-filter {
  width: 120px;
}

.rq-selected-count {
  font-size: var(--font-size-sm);
  color: var(--primary);
  font-weight: 500;
}

.rq-trust-pct {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  width: 32px;
}

.rq-empty {
  text-align: center;
  padding: var(--space-6);
  color: var(--muted-foreground);
}

.rq-pagination {
  margin-top: var(--space-4);
  display: flex;
  justify-content: center;
}

.flex-1 {
  flex: 1;
}

@media (max-width: 768px) {
  .rq-action-bar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
