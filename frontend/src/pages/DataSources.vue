<script setup lang="ts">
/**
 * 数据源管理页 — Sprint 1.2
 * 网格卡片布局展示数据源，含权威度仪表盘、统计、操作按钮
 */
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight, CircleCheckFilled, WarningFilled } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import BusinessBanner from '@/components/BusinessBanner.vue'
import DataSourceSummary from '@/components/DataSourceSummary.vue'
import DataSourceCard from '@/components/DataSourceCard.vue'
import ManualImportDialog from '@/components/ManualImportDialog.vue'
import { useDataSourceStore } from '@/stores/datasource'
import { getSourceNameLabel } from '@/composables/useDataSourceCharts'

const dsStore = useDataSourceStore()

// --- 健康状态横幅 ---
const healthBanner = computed(() => {
  const h = dsStore.health
  if (!h) return null
  if (h.error_sources > 0) {
    return {
      type: 'warning' as const,
      title: `${h.error_sources} 个数据源异常`,
      desc: `共 ${h.total_sources} 个数据源，${h.active_sources} 个活跃，${h.error_sources} 个异常需关注`,
    }
  }
  return {
    type: 'success' as const,
    title: '全部数据源正常',
    desc: `${h.active_sources} 个活跃数据源运行正常`,
  }
})

// --- 同步 ---
const syncingIds = ref(new Set<string>())
async function handleSync(sourceId: string, sourceName: string) {
  if (syncingIds.value.has(sourceId)) return
  syncingIds.value.add(sourceId)
  try {
    const ok = await dsStore.triggerSync(sourceId)
    ElMessage[ok ? 'success' : 'error'](`${getSourceNameLabel(sourceName)} ${ok ? '同步已触发' : '同步失败'}`)
    if (ok) void dsStore.fetchSources()
  } catch {
    ElMessage.error(`${getSourceNameLabel(sourceName)} 同步失败`)
  } finally { syncingIds.value.delete(sourceId) }
}

// --- 立即采集 ---
async function handleImmediateCrawl(sourceId: string, sourceName: string) {
  if (syncingIds.value.has(sourceId)) return
  syncingIds.value.add(sourceId)
  try {
    const crawlingMsg = ElMessage.info({ message: `${getSourceNameLabel(sourceName)} 正在在线爬取最新职位（约 30-90 秒）...`, duration: 4000 })
    const out = await dsStore.triggerCrawl(sourceName) as { fetched?: number; inserted?: number; duplicate?: number; error_samples?: Array<{ source: string; hash_prefix: string; error: string }> }
    crawlingMsg.close()
    const fetched = out?.fetched ?? 0
    const inserted = out?.inserted ?? 0
    const duplicate = out?.duplicate ?? 0
    if (out?.error_samples?.length) {
      ElMessage.error(`${getSourceNameLabel(sourceName)} 采集 ${inserted} 条，${duplicate} 条已存在；写入失败: ${out.error_samples[0].error}`)
    } else if (fetched === 0) {
      ElMessage.warning(`${getSourceNameLabel(sourceName)} 立即采集：本次未获取到职位（远程平台可能限流或暂无数据）`)
    } else if (inserted > 0) {
      ElMessage.success(
        `${getSourceNameLabel(sourceName)} 立即采集完成: 在线获取 ${fetched} 条，新增 ${inserted} 条` +
        `${duplicate ? `，${duplicate} 条已存在` : ''}。新增岗位/技能将进入管理后台「内容审核」待审队列。`,
      )
    } else {
      ElMessage.success(`${getSourceNameLabel(sourceName)} 已在线确认最新 ${fetched} 条职位均已在库（平台暂无新职位），最后同步时间已刷新`)
    }
    dsStore.fetchSources()
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail ? `${getSourceNameLabel(sourceName)} 立即采集失败：${detail}` : `${getSourceNameLabel(sourceName)} 立即采集失败`)
  } finally {
    syncingIds.value.delete(sourceId)
  }
}

// --- 手动导入 ---
const importDialogVisible = ref(false)
const importSource = ref<{ id: string; name: string }>({ id: '', name: '' })
function openImportDialog(source: { id: string; name: string }) {
  importSource.value = source
  importDialogVisible.value = true
}

// --- 恢复暂停源 (2026-08-20) ---
const activatingIds = ref(new Set<string>())
async function handleActivate(sourceId: string, sourceName: string) {
  if (activatingIds.value.has(sourceId)) return
  activatingIds.value.add(sourceId)
  try {
    const ok = await dsStore.activateSource(sourceId)
    ElMessage[ok ? 'success' : 'error'](`${getSourceNameLabel(sourceName)} ${ok ? '已恢复（进入采集调度）' : '恢复失败'}`)
    void dsStore.fetchSources()
  } catch {
    ElMessage.error(`${getSourceNameLabel(sourceName)} 恢复失败`)
  } finally { activatingIds.value.delete(sourceId) }
}

onMounted(() => {
  dsStore.fetchSources()
  // 健康状态非 admin 也能看（降级为空），静默获取
  dsStore.fetchHealth().catch(() => {})
})
</script>

<template>
  <MainLayout>
    <div class="datasources-page animate-fade-in">
      <BusinessBanner
        type="info"
        title="数据源管理"
        description="管理 StarMap 用到的所有数据源：官方标准（ESCO）、招聘 JD、技术博客。每个数据源都有一个权威性评分，越权威的数据对岗位/技能信任度评分的影响越大。"
        meta="后端: <code>/datasources</code> · 数据源: <code>datasources</code> 表 · 采集 → 归一化 → 信任度评分"
      />

      <!-- 页面头部 -->
      <div class="page-header">
        <div>
          <h2>数据源管理</h2>
          <p class="page-desc">
            管理多源数据融合：爬虫采集 / API 接入 / 手动导入
          </p>
        </div>
        <div class="header-actions">
          <el-button
            size="small"
            :icon="RefreshRight"
            :loading="dsStore.loading"
            @click="dsStore.fetchSources()"
          >
            刷新
          </el-button>
        </div>
      </div>

      <!-- KPI 汇总 -->
      <DataSourceSummary
        :sources="dsStore.sources"
        :loading="dsStore.loading"
      />

      <!-- 健康状态横幅 -->
      <el-alert
        v-if="healthBanner"
        :type="healthBanner.type"
        :closable="false"
        show-icon
        class="mb-4"
      >
        <template #title>
          <span style="display: inline-flex; align-items: center; gap: 6px;">
            <el-icon v-if="healthBanner.type === 'success'"><CircleCheckFilled /></el-icon>
            <el-icon v-else><WarningFilled /></el-icon>
            {{ healthBanner.title }}
          </span>
        </template>
        <template #default>
          {{ healthBanner.desc }}
        </template>
      </el-alert>

      <!-- 数据源卡片网格 -->
      <el-row
        v-loading="dsStore.loading"
        :gutter="16"
      >
        <el-col
          v-if="!dsStore.loading && dsStore.sources.length === 0"
          :span="24"
        >
          <el-empty description="暂无数据源（请检查后端 DataSourceRecord 表）" />
        </el-col>

        <el-col
          v-for="source in dsStore.sources.filter(s => s.status !== 'inactive')"
          :key="source.id"
          :xl="8"
          :lg="12"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <DataSourceCard
            :source="source"
            :syncing="syncingIds.has(source.id)"
            @sync="handleSync(source.id, source.name)"
            @crawl="handleImmediateCrawl(source.id, source.name)"
            @manual-import="openImportDialog(source)"
            @activate="handleActivate(source.id, source.name)"
          />
        </el-col>
      </el-row>

      <!-- 手动导入弹窗 -->
      <ManualImportDialog
        v-model:visible="importDialogVisible"
        :source-id="importSource.id"
        :source-name="importSource.name"
        @imported="dsStore.fetchSources()"
      />
    </div>
  </MainLayout>
</template>

<style scoped>
.datasources-page {
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-6);
  flex-wrap: wrap;
  gap: var(--space-3);
}
.page-header h2 {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  color: var(--foreground);
  margin: 0 0 var(--space-1);
  letter-spacing: var(--tracking-tight);
}
.page-desc {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
  margin: 0;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.mb-4 { margin-bottom: var(--space-4); }
@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .header-actions { width: 100%; justify-content: flex-start; }
}
</style>
