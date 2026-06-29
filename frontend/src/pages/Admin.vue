<script setup lang="ts">
/**
 * 管理后台 — R6 曾洋涛
 * 审核队列（搜索/批量）+ 数据源配置 + 重置演示数据
 */
import { onMounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useAdminStore } from '@/stores/admin'

const admin = useAdminStore()

onMounted(() => {
  admin.fetchSources()
  admin.fetchAuditQueue()
})

// ── 搜索过滤 ──
const searchKeyword = ref('')
const typeFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const pagedAuditQueue = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredAuditQueue.value.slice(start, start + pageSize.value)
})

// ── 数据源编辑 ──
const editDialogVisible = ref(false)
const editingSource = ref<{ id: number; name: string; authority_score: number } | null>(null)
function handleEditSource(row: any) {
  editingSource.value = { id: row.id, name: row.name, authority_score: row.authority_score }
  editDialogVisible.value = true
}
function handleSaveSource() {
  if (!editingSource.value) return
  // Find and update in local state
  const idx = admin.sources.findIndex(s => s.id === editingSource.value!.id)
  if (idx !== -1) {
    admin.sources[idx] = { ...admin.sources[idx], name: editingSource.value.name, authority_score: editingSource.value.authority_score }
  }
  editDialogVisible.value = false
  ElMessage.success('数据源已更新')
}

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

// ── 重置演示数据 ──
async function handleReset() {
  try {
    await ElMessageBox.confirm(
      '确认重置为演示数据？当前所有数据将被清空并重新加载种子数据，此操作不可撤销。',
      '⚠️ 重置演示数据',
      { confirmButtonText: '确认重置', cancelButtonText: '取消', type: 'warning' }
    )
    await admin.resetToDemo()
    ElMessage.success('已重置为演示数据')
    admin.fetchSources()
    admin.fetchAuditQueue()
  } catch { /* 取消 */ }
}
</script>

<template>
  <MainLayout>
    <div class="admin-page">
      <div class="page-header">
        <div>
          <h2>管理后台</h2>
          <p class="page-desc">
            人工审核、数据源配置与演示数据管理
          </p>
        </div>
      </div>

      <!-- 操作栏 -->
      <el-card
        shadow="never"
        class="action-bar"
      >
        <div class="action-bar-inner">
          <div class="action-left">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索技能或岗位名..."
              :prefix-icon="Search"
              clearable
              style="width: 240px"
              size="default"
            />
            <el-select
              v-model="typeFilter"
              placeholder="按类型过滤"
              clearable
              style="width: 130px"
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
            <el-button
              type="danger"
              plain
              size="default"
              :icon="Delete"
              @click="handleReset"
            >
              重置演示数据
            </el-button>
          </div>
          <div class="action-right">
            <span
              v-if="selectedIds.size"
              class="selected-count"
            >
              已选 {{ selectedIds.size }} 条
            </span>
            <el-button
              size="default"
              type="success"
              :disabled="!selectedIds.size"
              @click="handleBatchApprove"
            >
              批量通过
            </el-button>
            <el-button
              size="default"
              type="danger"
              :disabled="!selectedIds.size"
              @click="handleBatchReject"
            >
              批量拒绝
            </el-button>
          </div>
        </div>
      </el-card>

      <!-- 审核 + 数据源 -->
      <el-row
        :gutter="16"
        style="margin-top: 16px"
      >
        <!-- 审核队列 -->
        <el-col
          :lg="14"
          :sm="24"
          style="margin-bottom: 16px"
        >
          <el-card
            shadow="never"
            header="人工审核队列"
          >
            <el-table
              ref="tableRef"
              v-loading="admin.loading"
              :data="pagedAuditQueue"
              stripe
              size="default"
              @selection-change="() => {}"
            >
              <el-table-column
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
                      style="flex: 1"
                    />
                    <span style="font-size: 12px; color: #909399; width: 32px">{{ row.trust }}%</span>
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
            <div
              v-if="!filteredAuditQueue.length"
              style="text-align: center; padding: 24px; color: #c0c4cc"
            >
              暂无匹配的审核项
            </div>
            <div v-if="filteredAuditQueue.length" style="margin-top: 16px; display: flex; justify-content: center;">
              <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="pageSize"
                :total="filteredAuditQueue.length"
                :page-sizes="[10, 20, 50]"
                layout="total, sizes, prev, pager, next"
                small
              />
            </div>
          </el-card>
        </el-col>

        <!-- 数据源配置 -->
        <el-col
          :lg="10"
          :sm="24"
          style="margin-bottom: 16px"
        >
          <el-card
            shadow="never"
            header="数据源配置"
          >
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
            </el-table>
          </el-card>
        </el-col>

        <!-- 数据源配置 -->
        <el-col
          :lg="10"
          :sm="24"
          style="margin-bottom: 16px"
        >
          <el-card
            shadow="never"
            style="margin-top: 16px"
          >
            <template #header>
              <span style="font-weight: 600">🔄 演示数据管理</span>
            </template>
            <p style="color: #606266; font-size: 13px; line-height: 1.8; margin: 0">
              重置为演示种子数据将覆盖当前所有数据，包括岗位、技能、图谱节点与关系。此功能用于演示场景重置（§16.5）。
            </p>
            <el-button
              type="danger"
              style="margin-top: 12px"
              :icon="Delete"
              @click="handleReset"
            >
              重置为演示数据
            </el-button>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </MainLayout>
</template>

<style scoped>
.admin-page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 4px;
}

.page-desc {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

/* ── 操作栏 ── */
.action-bar-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.action-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.action-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.selected-count {
  font-size: 13px;
  color: #409eff;
  font-weight: 500;
}

@media (max-width: 768px) {
  .action-bar-inner {
    flex-direction: column;
    align-items: stretch;
  }

  .action-left,
  .action-right {
    flex-wrap: wrap;
  }
}
</style>
