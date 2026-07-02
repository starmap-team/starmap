<script setup lang="ts">
/**
 * 岗位列表页 — 从后端 /positions 获取岗位数据
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import MainLayout from '@/layouts/MainLayout.vue'
import request from '@/api/request'

const router = useRouter()
const positions = ref<{ id: string; name: string; industry: string }[]>([])
const loading = ref(false)
const searchQuery = ref('')
const selectedIndustry = ref('')
const total = ref(0)
const page = ref(1)
const pageSize = ref(24)
const industries = computed(() => {
  const set = new Set(positions.value.map(p => p.industry))
  return Array.from(set).sort()
})
const filteredPositions = computed(() => {
  let list = positions.value
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(p =>
      p.name.toLowerCase().includes(q) || p.industry.toLowerCase().includes(q)
    )
  }
  if (selectedIndustry.value) {
    list = list.filter(p => p.industry === selectedIndustry.value)
  }
  return list
})

async function fetchPositions() {
  loading.value = true
  try {
    const data = await request.get('/positions', { params: { page: page.value, page_size: pageSize.value } }) as any
    const items = data.items ?? data ?? []
    positions.value = items.map((p: any) => ({
      id: p.position_id ?? p.id ?? '',
      name: p.name ?? '',
      industry: p.industry ?? '互联网 IT',
    }))
    total.value = data.total ?? items.length
  } catch (e) {
    console.error('[PositionList] Failed to fetch:', e)
    ElMessage.error('岗位列表加载失败，请确认后端服务已启动')
  } finally {
    loading.value = false
  }
}

function onPageChange(newPage: number) {
  page.value = newPage
  fetchPositions()
}

function onSearch() {
  page.value = 1
  fetchPositions()
}

function goDetail(name: string) {
  router.push(`/position/${encodeURIComponent(name)}`)
}

function goExtract() {
  router.push('/extract')
}

onMounted(fetchPositions)
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
        prefix-icon="Search"
      />
      <div class="industry-tags">
        <el-tag
          :type="selectedIndustry === '' ? '' : 'info'"
          :effect="selectedIndustry === '' ? 'dark' : 'plain'"
          class="clickable-tag"
          @click="selectedIndustry = ''"
        >
          全部
        </el-tag>
        <el-tag
          v-for="ind in industries"
          :key="ind"
          :type="selectedIndustry === ind ? '' : 'info'"
          :effect="selectedIndustry === ind ? 'dark' : 'plain'"
          class="clickable-tag"
          @click="selectedIndustry = selectedIndustry === ind ? '' : ind"
        >
          {{ ind }}
        </el-tag>
      </div>
      <div class="result-count">
        共 {{ filteredPositions.length }} 个岗位
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
            @click="goDetail(pos.name)"
          >
            <div class="card-content">
              <h3>{{ pos.name }}</h3>
              <el-tag
                size="small"
                type="info"
              >
                {{ pos.industry }}
              </el-tag>
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
          <p class="empty-text">
            未找到匹配的岗位
          </p>
          <p class="empty-hint-text">
            尝试调整筛选条件或关键词
          </p>
          <div class="empty-actions">
            <p class="empty-hint-text">
              请先执行数据采集，或从 JD 中抽取岗位信息
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
  font-size: var(--font-size-3xl);
  font-weight: 800;
  letter-spacing: var(--tracking-tight);
  margin: 0 0 4px;
  font-size: var(--font-size-2xl);
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
.empty-text {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}
.empty-hint-text {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
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