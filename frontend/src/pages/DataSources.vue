<script setup lang="ts">
/**
 * 数据源管理页 — Sprint 1.2
 * 网格卡片布局展示5个数据源（BOSS/拉勾/51Job/GitHub/ESCO）
 * 每个卡片含：权威度评分环形图、日采集量柱状图、数据质量评分、最后同步时间、一键同步按钮
 */
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Coin, DataLine, RefreshRight, WarningFilled } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GaugeChart, BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent } from 'echarts/components'
import MainLayout from '@/layouts/MainLayout.vue'
import BusinessBanner from '@/components/BusinessBanner.vue'
import { useDataSourceStore } from '@/stores/datasource'
import { chartColors } from '@/utils/chartTheme'
import { asTagType } from '@/utils/element'
import {
  getAuthorityGaugeOption,
  getDailyVolumeOption,
  getStatusBadge,
  getSourceTypeLabel,
  formatLastCrawl,
  formatRecords,
  getSourceNameLabel,
} from '@/composables/useDataSourceCharts'

use([GaugeChart, BarChart, TooltipComponent, GridComponent])

const dsStore = useDataSourceStore()
// ponytail: chartColors re-exported for template KPI card :style bindings
const cc = chartColors()

// DataSource sync + summary (inlined from useDataSourceActions + useDataSourceSummary)
const syncingIds = ref(new Set<string>())
function isSyncing(id: string) { return syncingIds.value.has(id) }
async function handleSync(source: typeof dsStore.sources[number]) {
  if (syncingIds.value.has(source.id)) return
  syncingIds.value.add(source.id)
  try { const ok = await dsStore.triggerSync(source.id); ElMessage[ok ? 'success' : 'error'](`${getSourceNameLabel(source.name)} ${ok ? '同步已触发' : '同步失败'}`) }
  catch { ElMessage.error(`${getSourceNameLabel(source.name)} 同步失败`) }
  finally { syncingIds.value.delete(source.id) }
}
// Phase 15 / T2.3: 按需触发单源采集 → raw_jd_records
async function handleImmediateCrawl(source: typeof dsStore.sources[number]) {
  if (syncingIds.value.has(source.id)) return
  syncingIds.value.add(source.id)
  try {
    // map source.name -> source site key (BOSS, 拉勾, 猎聘, remotive, v2ex)
    const key = source.name.includes('Boss') ? 'BOSS' : source.name
    const out = await dsStore.triggerCrawl(key) as { fetched?: number; persisted?: number; rows?: { title: string }[] }
    ElMessage.success(
      `${getSourceNameLabel(source.name)} 立即采集完成: fetched=${out?.fetched ?? 0} persisted=${out?.persisted ?? 0}`
    )
    dsStore.fetchSources()  // refresh last_crawl_at
  } catch {
    ElMessage.error(`${getSourceNameLabel(source.name)} 立即采集失败`)
  } finally {
    syncingIds.value.delete(source.id)
  }
}
const summaryStats = computed(() => {
  const src = dsStore.sources
  return { total: src.length, active: src.filter((s: any) => s.status === 'active').length, totalRecords: src.reduce((sum: number, s: any) => sum + s.total_records, 0), avgQuality: src.length ? src.reduce((sum: number, s: any) => sum + s.avg_quality_score, 0) / src.length : 0 }
})

onMounted(() => {
  dsStore.fetchSources()
})
</script>

<template>
  <MainLayout>
    <div class="datasources-page animate-fade-in">
      <BusinessBanner
        type="info"
        title="多源异构数据融合 — 数据源管理"
        description="StarMap 融合三类异构数据源：结构化（ESCO 职业标准）、半结构化（招聘 JD 爬虫）、非结构化（技术博客）。权威性评分直接影响 §7.1 信任度驱动的图谱构建策略。"
        meta="后端: <code>/datasources</code> · 数据源: <code>datasources</code> 表 · 采集 → 归一化 → 信任度评分"
      />

      <!-- 页面头部 -->
      <div class="page-header">
        <div>
          <h2>数据源管理</h2>
          <p class="page-desc">
            管理多源数据融合：BOSS直聘 / 拉勾 / 51Job / GitHub / ESCO
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

      <!-- 汇总 KPI -->
      <el-row
        :gutter="16"
        class="mb-4"
      >
        <el-col
          :lg="6"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="kpi-card"
          >
            <div class="kpi-inner">
              <div
                class="kpi-icon"
                :style="{ background: cc.primary + '18', color: cc.primary }"
              >
                <el-icon size="22">
                  <Connection />
                </el-icon>
              </div>
              <div class="kpi-body">
                <div class="kpi-label">
                  数据源总数
                </div>
                <div
                  class="kpi-value"
                  :style="{ color: cc.primary }"
                >
                  {{ summaryStats.total }}
                </div>
                <div class="kpi-sub">
                  {{ summaryStats.active }} 个活跃
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col
          :lg="6"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="kpi-card"
          >
            <div class="kpi-inner">
              <div
                class="kpi-icon"
                :style="{ background: cc.success + '18', color: cc.success }"
              >
                <el-icon size="22">
                  <Coin />
                </el-icon>
              </div>
              <div class="kpi-body">
                <div class="kpi-label">
                  总记录量
                </div>
                <div
                  class="kpi-value"
                  :style="{ color: cc.success }"
                >
                  {{ formatRecords(summaryStats.totalRecords) }}
                </div>
                <div class="kpi-sub">
                  条已入库
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col
          :lg="6"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="kpi-card"
          >
            <div class="kpi-inner">
              <div
                class="kpi-icon"
                :style="{ background: cc.info + '18', color: cc.info }"
              >
                <el-icon size="22">
                  <DataLine />
                </el-icon>
              </div>
              <div class="kpi-body">
                <div class="kpi-label">
                  平均质量分
                </div>
                <div
                  class="kpi-value"
                  :style="{ color: summaryStats.avgQuality >= 0.8 ? cc.success : cc.warning }"
                >
                  {{ (summaryStats.avgQuality * 100).toFixed(1) }}%
                </div>
                <div class="kpi-sub">
                  <span :class="summaryStats.avgQuality >= 0.8 ? 'trend-up' : 'trend-down'">
                    {{ summaryStats.avgQuality >= 0.8 ? '▲' : '▼' }}
                  </span>
                  {{ summaryStats.avgQuality >= 0.8 ? '质量优秀' : '有提升空间' }}
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col
          :lg="6"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="kpi-card"
          >
            <div class="kpi-inner">
              <div
                class="kpi-icon"
                :style="{ background: cc.warning + '18', color: cc.warning }"
              >
                <el-icon size="22">
                  <WarningFilled />
                </el-icon>
              </div>
              <div class="kpi-body">
                <div class="kpi-label">
                  异常数据源
                </div>
                <div
                  class="kpi-value"
                  :style="{ color: summaryStats.total - summaryStats.active > 0 ? cc.danger : cc.success }"
                >
                  {{ summaryStats.total - summaryStats.active }}
                </div>
                <div class="kpi-sub">
                  {{ summaryStats.total - summaryStats.active > 0 ? '需关注' : '全部正常' }}
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 数据源卡片网格 -->
      <el-row
        v-loading="dsStore.loading"
        :gutter="16"
      >
        <!-- M5：无数据源时显式空态（避免空 el-row 被误读为"加载中"） -->
        <el-col v-if="!dsStore.loading && dsStore.sources.length === 0" :span="24">
          <el-empty
            description="暂无数据源（请检查后端 DataSourceRecord 表）"
          />
        </el-col>
        <!-- M5：源存在但全部 records=0 时，给出"未采集"提示，避免 KPI 0/0/0 被误读为"质量差" -->
        <el-col
          v-else-if="!dsStore.loading && dsStore.sources.length > 0 && summaryStats.totalRecords === 0"
          :span="24"
        >
          <el-alert
            type="info"
            :closable="false"
            show-icon
            title="数据源均无采集记录（待同步）"
            description="所有数据源尚未触发过 crawl/sync，记录数=0。点击卡片底部“立即同步”启动首次采集；这是“未采集”状态，非“数据质量差”。"
            class="mb-4"
          />
        </el-col>
        <el-col
          v-for="source in dsStore.sources"
          :key="source.id"
          :xl="8"
          :lg="12"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="source-card"
          >
            <!-- 卡片头部 -->
            <div class="card-header">
              <div class="card-title-group">
                <span class="card-name">{{ getSourceNameLabel(source.name) }}</span>
                <el-tag
                  :type="asTagType(getStatusBadge(source.status).type)"
                  size="small"
                  effect="light"
                  round
                >
                  {{ getStatusBadge(source.status).label }}
                </el-tag>
              </div>
              <el-tag
                size="small"
                effect="plain"
                round
              >
                {{ getSourceTypeLabel(source.source_type) }}
              </el-tag>
              <!-- Phase 13 数据诚实化：零记录须显式标注为空态，避免被误读为数据异常 -->
              <el-tag
                v-if="source.total_records === 0 && !source.last_crawl_at"
                size="small"
                type="warning"
                effect="plain"
                round
                title="该数据源尚未执行过采集，下方记录/质量数值为 0 属正常空态，非数据异常"
              >
                尚未采集
              </el-tag>
              <el-tag
                v-else-if="source.total_records === 0"
                size="small"
                type="info"
                effect="plain"
                round
              >
                暂无记录
              </el-tag>
            </div>

            <!-- 权威度环形图 + 统计信息 -->
            <div class="card-body">
              <div class="card-gauge">
                <VChart
                  :option="getAuthorityGaugeOption(source.authority_score)"
                  style="width: 130px; height: 110px;"
                  autoresize
                />
              </div>
              <div class="card-stats">
                <div class="stat-row">
                  <span class="stat-label">数据质量</span>
                  <span
                    class="stat-value"
                    :style="{ color: source.avg_quality_score >= 0.8 ? cc.success : cc.warning }"
                  >{{ (source.avg_quality_score * 100).toFixed(0) }}%</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">记录总量</span>
                  <span class="stat-value">{{ formatRecords(source.total_records) }}</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">有效记录</span>
                  <span class="stat-value">{{ source.valid_records.toLocaleString() }}</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">重复率</span>
                  <span
                    class="stat-value"
                    :style="{ color: source.duplicate_rate > 0.2 ? cc.danger : cc.success }"
                  >{{ (source.duplicate_rate * 100).toFixed(1) }}%</span>
                </div>
              </div>
            </div>

            <!-- 日采集量柱状图 -->
            <div class="card-chart">
              <div class="chart-label">
                日采集量
              </div>
              <VChart
                v-if="source.daily_crawl_volume?.length"
                :option="getDailyVolumeOption(source.daily_crawl_volume)"
                style="height: 100px;"
                autoresize
              />
              <div
                v-else
                class="chart-placeholder"
              >
                <span>暂无采集数据</span>
              </div>
            </div>

            <!-- 底部：同步时间 + 操作按钮 -->
            <div class="card-footer">
              <span class="sync-time">
                最后同步：{{ formatLastCrawl(source.last_crawl_at) }}
              </span>
              <el-button
                size="small"
                type="primary"
                :loading="syncingIds.has(source.id)"
                :disabled="source.status === 'paused'"
                @click="handleSync(source)"
              >
                <el-icon
                  v-if="!syncingIds.has(source.id)"
                  class="el-icon--left"
                >
                  <RefreshRight />
                </el-icon>
                {{ syncingIds.has(source.id) ? '同步中...' : '一键同步' }}
              </el-button>
              <el-button
                size="small"
                type="warning"
                plain
                :disabled="source.status === 'paused'"
                @click="handleImmediateCrawl(source)"
              >
                立即采集
              </el-button>
            </div>
          </el-card>
        </el-col>

        <!-- 空状态 -->
        <el-col
          v-if="!dsStore.loading && !dsStore.sources.length"
          :span="24"
        >
          <el-card
            shadow="never"
            class="empty-card"
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
                >
                  <ellipse
                    cx="12"
                    cy="5"
                    rx="9"
                    ry="3"
                  />
                  <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
                  <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
                </svg>
              </div>
              <p class="starmap-empty">
                数据源待加载
              </p>
              <p class="starmap-empty--hint">
                数据源信息将在首次同步后展示
              </p>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </MainLayout>
</template>

<style scoped>
.datasources-page {
  max-width: 1200px;
  margin: 0 auto;
}

/* Phase 26: 业务说明横幅 — 已迁移到 BusinessBanner.vue */


/* 页面头部 */
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

/* KPI 卡片 */
.kpi-card {
  cursor: default;
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}
.kpi-card::before {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 4%, transparent), transparent);
  transition: opacity var(--duration-normal);
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.kpi-card:hover::before { opacity: 1; }
.kpi-inner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  position: relative;
  z-index: 1;
}
.kpi-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.kpi-body {
  flex: 1;
  min-width: 0;
}
.kpi-label {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  font-weight: 500;
}
.kpi-value {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: var(--tracking-tight);
  font-variant-numeric: tabular-nums;
}
.kpi-sub {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  margin-top: var(--space-1);
}
.trend-up {
  color: var(--success);
  font-weight: 600;
}
.trend-down {
  color: var(--destructive);
  font-weight: 600;
}

/* 数据源卡片 */
.source-card {
  transition: all var(--duration-normal) var(--ease-out);
  height: 100%;
}
.source-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
  gap: var(--space-2);
}
.card-title-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.card-name {
  font-size: var(--font-size-lg);
  font-weight: 700;
  color: var(--foreground);
  letter-spacing: var(--tracking-tight);
}

/* 卡片主体：权威度 + 统计 */
.card-body {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.card-gauge {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.card-stats {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.stat-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
.stat-value {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--foreground);
  font-variant-numeric: tabular-nums;
}

/* 日采集量图表 */
.card-chart {
  margin-bottom: var(--space-3);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
}
.chart-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--muted-foreground);
  margin-bottom: var(--space-1);
}
.chart-placeholder {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted-foreground);
  font-size: var(--font-size-xs);
  opacity: 0.5;
}

/* 卡片底部 */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
}
.sync-time {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

/* 空状态 */
.empty-card {
  min-height: 300px;
}
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-8) var(--space-4);
  text-align: center;
}
.empty-icon-wrapper {
  color: var(--muted-foreground);
  opacity: 0.4;
  margin-bottom: var(--space-3);
}
.empty-text {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
}
.empty-hint-text {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}

.mb-4 { margin-bottom: var(--space-4); }

/* 响应式 */
@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .header-actions { width: 100%; justify-content: flex-start; }
  .kpi-value { font-size: var(--font-size-2xl); }
  .card-body { flex-direction: column; text-align: center; }
  .card-stats { width: 100%; }
}
</style>


