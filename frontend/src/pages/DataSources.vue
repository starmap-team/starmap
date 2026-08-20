<script setup lang="ts">
/**
 * 数据源管理页 — Sprint 1.2
 * 网格卡片布局展示5个数据源（BOSS/拉勾/51Job/GitHub/ESCO）
 * 每个卡片含：权威度评分环形图、日采集量柱状图、数据质量评分、最后同步时间、一键同步按钮
 */
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Coin, DataLine, RefreshRight, WarningFilled, Upload } from '@element-plus/icons-vue'
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
  getStatusBadge,
  getSourceTypeLabel,
  formatLastCrawl,
  formatRecords,
  getSourceNameLabel,
} from '@/composables/useDataSourceCharts'
import { SOURCE_DESCRIPTIONS, isCrawlableSource } from '@/constants/labels'

use([GaugeChart, BarChart, TooltipComponent, GridComponent])

const dsStore = useDataSourceStore()
// ponytail: chartColors re-exported for template KPI card :style bindings
const cc = chartColors()

// DataSource sync + summary (inlined from useDataSourceActions + useDataSourceSummary)
const syncingIds = ref(new Set<string>())
async function handleSync(source: typeof dsStore.sources[number]) {
  if (syncingIds.value.has(source.id)) return
  syncingIds.value.add(source.id)
  try {
    const ok = await dsStore.triggerSync(source.id)
    ElMessage[ok ? 'success' : 'error'](`${getSourceNameLabel(source.name)} ${ok ? '同步已触发' : '同步失败'}`)
    // fix: 同步成功后刷新列表（triggerSync 只刷 detail），使卡片"最后同步"时间可见更新
    if (ok) void dsStore.fetchSources()
  } catch {
    ElMessage.error(`${getSourceNameLabel(source.name)} 同步失败`)
  } finally { syncingIds.value.delete(source.id) }
}
// T2.5: 手动导入 JD（无爬虫适配器时的兜底入口）
async function handleManualImport(source: typeof dsStore.sources[number]) {
  const raw = window.prompt(
    `手动导入到「${source.name}」,每行一个 JD JSON (必填 source_url/raw_text/title):`,
    '[{"source_url":"https://example.com/j1","raw_text":"...","title":"前端开发工程师","company":"ACME"}]'
  )
  if (!raw) return
  let jds: unknown[] = []
  try { jds = JSON.parse(raw) } catch (e) {
    ElMessage.error('JSON 解析失败: ' + (e as Error).message); return
  }
  if (!Array.isArray(jds) || jds.length === 0) { ElMessage.error('请提供非空 JD 数组'); return }
  try {
    const out = await (dsStore as any).api.post(`/datasources/${source.id}/manual-import`, { jds }) as {
      inserted: number; duplicates: number; errors: string[]
    }
    if (out.errors && out.errors.length) {
      ElMessage.warning(`已导入 ${out.inserted} 条, ${out.duplicates} 条重复, 错误 ${out.errors.length} 条`)
    } else {
      ElMessage.success(`✅ 已导入 ${out.inserted} 条到「${source.name}」`)
    }
    void dsStore.fetchSources()
  } catch (e) {
    ElMessage.error('手动导入失败: ' + ((e as any)?.response?.data?.detail || (e as Error).message))
  }
}
// / T2.3: 按需触发单源采集 → raw_jd_records
async function handleImmediateCrawl(source: typeof dsStore.sources[number]) {
  if (syncingIds.value.has(source.id)) return
  syncingIds.value.add(source.id)
  try {
    // ponytail: 原实现把 Boss 特判为 'BOSS'，其余源传显示名；
    // 后端 /pipeline/crawl-source 按 DataSourceRecord.name 精确匹配（routes.py:475），
    // 特判会导致 DB 名称非 'BOSS' 时 404 —— 直接传 source.name 即可
    const key = source.name
    // D5: 点击即提示"正在在线爬取"，避免 30-60s 等待期看起来无响应
    const crawlingMsg = ElMessage.info({ message: `${getSourceNameLabel(source.name)} 正在在线爬取最新职位（约 30-90 秒）...`, duration: 4000 })
    const out = await dsStore.triggerCrawl(key) as { fetched?: number; inserted?: number; duplicate?: number; failed?: number; error_samples?: Array<{ source: string; hash_prefix: string; error: string }> }
    crawlingMsg.close()
    const fetched = out?.fetched ?? 0
    const inserted = out?.inserted ?? 0
    const duplicate = out?.duplicate ?? 0
    if (out?.error_samples?.length) {
      // D5: 错误穿透 —— 展示 dao 层真实异常，不再沉默
      const first = out.error_samples[0]
      ElMessage.error(`${getSourceNameLabel(source.name)} 采集 ${inserted} 条，${duplicate} 条已存在；写入失败: ${first.error}`)
    } else if (fetched === 0) {
      ElMessage.warning(`${getSourceNameLabel(source.name)} 立即采集：本次未获取到职位（远程平台可能限流或暂无数据）`)
    } else if (inserted > 0) {
      ElMessage.success(
        `${getSourceNameLabel(source.name)} 立即采集完成: 在线获取 ${fetched} 条，新增 ${inserted} 条` +
        `${duplicate ? `，${duplicate} 条已存在` : ''}。新增岗位/技能将进入管理后台「内容审核」待审队列。`,
      )
    } else {
      // 全重复 = 已在线确认平台最新职位均已在库（非失败）
      ElMessage.success(`${getSourceNameLabel(source.name)} 已在线确认最新 ${fetched} 条职位均已在库（平台暂无新职位），最后同步时间已刷新`)
    }
    dsStore.fetchSources()  // refresh last_crawl_at
  } catch (e: unknown) {
    // 展示后端具体原因（如"未配置爬虫平台"），而非笼统失败
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail ? `${getSourceNameLabel(source.name)} 立即采集失败：${detail}` : `${getSourceNameLabel(source.name)} 立即采集失败`)
  } finally {
    syncingIds.value.delete(source.id)
  }
}
// M2/M3 (2026-08-15): 软删除源（inactive）不展示——避免"同名不同状态"卡与
// KPI 虚高（数据源总数 19 含 3 个已归档占位 → 应 16）。
// Task 8 (DC-04): status 全集与后端共享枚举
// app.core.constants.DataSourceStatus（active/paused/error/inactive）对齐——
// 'inactive' 由 DELETE 软删除 / PATCH 产出，UI 过滤属展示层约定，非校验兜底。
const visibleSources = computed(() => dsStore.sources.filter((s) => s.status !== 'inactive'))
const summaryStats = computed(() => {
  const src = visibleSources.value
  // fix: 异常口径只计 error（paused 为人为主观停用，非异常）—— datasource 优化设计需求 C
  // fix: 平均质量分只对"已评估"(avg_quality_score>0) 源求均值；全未评估 → null（诚实"未评估"）
  //      而非把 0 计入平均 → 假"0.0% ▼ 有提升空间"（2026-08-12 D4 多端语义验证）
  const evaluated = src.filter((s) => s.avg_quality_score > 0)
  const avgQuality = evaluated.length
    ? evaluated.reduce((sum: number, s) => sum + s.avg_quality_score, 0) / evaluated.length
    : null
  return {
    total: src.length,
    active: src.filter((s) => s.status === 'active').length,
    error: src.filter((s) => s.status === 'error').length,
    evaluatedCount: evaluated.length,
    totalRecords: src.reduce((sum: number, s) => sum + s.total_records, 0),
    avgQuality,
  }
})

// 卡片"数据质量"诚实态：已评估 → X%；有记录但未抽取 → 未评估；无记录 → 未评估
// D2 (2026-08-15): 0 记录源的质量分是残留值（seed/历史 avg_quality_score），
// 纯 UI 隐藏为"未评估"，避免"暂无记录 + 质量 90%"矛盾。
function formatQuality(s: { avg_quality_score: number; total_records: number }): string {
  if (s.total_records === 0) return '未评估'
  if (s.avg_quality_score > 0) return `${(s.avg_quality_score * 100).toFixed(0)}%`
  return '未评估'
}

// D2: 卡片状态徽章 —— 未配置适配器的 active 源显示"未配置"而非"运行中"
function cardStatusBadge(s: { status: string; has_adapter?: boolean }) {
  if (s.status === 'active' && s.has_adapter === false) {
    return { type: 'warning' as const, label: '未配置' }
  }
  return getStatusBadge(s.status)
}

onMounted(() => {
  dsStore.fetchSources()
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
                  :style="{ color: summaryStats.avgQuality === null ? cc.info : (summaryStats.avgQuality >= 0.8 ? cc.success : cc.warning) }"
                >
                  {{ summaryStats.avgQuality === null ? '未评估' : `${(summaryStats.avgQuality * 100).toFixed(1)}%` }}
                </div>
                <div class="kpi-sub">
                  <template v-if="summaryStats.avgQuality !== null">
                    <span :class="summaryStats.avgQuality >= 0.8 ? 'trend-up' : 'trend-down'">
                      {{ summaryStats.avgQuality >= 0.8 ? '▲' : '▼' }}
                    </span>
                    {{ summaryStats.avgQuality >= 0.8 ? '质量优秀' : '有提升空间' }}
                    <span v-if="summaryStats.evaluatedCount < summaryStats.total">（{{ summaryStats.evaluatedCount }}/{{ summaryStats.total }} 已评估）</span>
                  </template>
                  <template v-else>
                    尚无已评估数据源
                  </template>
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
                  :style="{ color: summaryStats.error > 0 ? cc.danger : cc.success }"
                >
                  {{ summaryStats.error }}
                </div>
                <div class="kpi-sub">
                  {{ summaryStats.error > 0 ? '需关注' : '全部正常' }}
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
        <el-col
          v-if="!dsStore.loading && dsStore.sources.length === 0"
          :span="24"
        >
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
          v-for="source in visibleSources"
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
                  :type="asTagType(cardStatusBadge(source).type)"
                  size="small"
                  effect="light"
                  round
                >
                  {{ cardStatusBadge(source).label }}
                </el-tag>
              </div>
              <!-- D5 UX: 数据源说明 —— 告诉用户这个源是什么 -->
              <p class="card-desc">
                {{ SOURCE_DESCRIPTIONS[source.name] ?? '外部数据源' }}
              </p>
              <div class="card-tags">
                <el-tag
                  size="small"
                  effect="plain"
                  round
                >
                  {{ getSourceTypeLabel(source.source_type) }}
                </el-tag>
                <!-- ESCO 标准库非爬虫源：不展示「立即采集」，用标签说明 -->
                <el-tag
                  v-if="source.source_type === 'esco'"
                  size="small"
                  type="info"
                  effect="plain"
                  round
                >
                  标准库 · 无需采集
                </el-tag>
                <!-- D6: juejin 技术博客源（非岗位 JD）——语义化标注，立即采集抓取的是技术文章 -->
                <el-tag
                  v-if="source.source_type === 'blog'"
                  size="small"
                  type="warning"
                  effect="plain"
                  round
                  title="该源抓取技术博客文章作为非结构化技能知识源，非招聘 JD"
                >
                  技术博客源 · 非岗位 JD
                </el-tag>
                <!-- 数据诚实化：零记录须显式标注为空态，避免被误读为数据异常 -->
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
                    :title="source.avg_quality_score > 0 ? '有效记录 / (有效+重复) 的抽取质量' : (source.total_records > 0 ? '有记录但尚未抽取，质量未评估' : '尚未采集，无数据可评估')"
                    :style="{ color: source.avg_quality_score > 0 ? (source.avg_quality_score >= 0.8 ? cc.success : cc.warning) : cc.info }"
                  >{{ formatQuality(source) }}</span>
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

            <!-- fix: 移除"日采集量"卡片柱状图 —— 后端列表响应从不返回 daily_crawl_volume，
                 恒显占位符的死 UI（datasource 优化设计需求 B）。真实按源采集量由
                 Admin 统计抽屉 fetchStats → crawl_volume 提供 -->

            <!-- 底部：同步时间 + 操作按钮 -->
            <div class="card-footer">
              <span class="sync-time">
                {{ source.total_records > 0 ? '最后同步' : '最近尝试' }}：{{ formatLastCrawl(source.last_crawl_at) }}
              </span>
              <!-- D5 UX: 一键同步 tooltip —— 说明触发的是完整流水线 -->
              <el-tooltip
                placement="top"
                :show-after="200"
              >
                <template #content>
                  触发该数据源完整流水线：爬取 → 去重 → 清洗 → 技能抽取 → 写入图谱（通常 30-90 秒，完成后记录/质量自动更新）
                </template>
                <el-button
                  size="small"
                  type="primary"
                  :loading="syncingIds.has(source.id)"
                  :disabled="!source.has_adapter || source.status === 'paused' || source.status === 'inactive'"
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
                <!-- D6 新增：手动导入按钮 (类型=manual 时可用) -->
                <el-button
                  v-if="source.source_type === 'manual'"
                  size="small"
                  type="success"
                  plain
                  @click="handleManualImport(source)"
                >
                  <el-icon class="el-icon--left"><Upload /></el-icon>
                  手动导入
                </el-button>
              </el-tooltip>
              <!-- D5 UX: 立即采集仅对可爬取源启用；未配置平台禁用并说明原因；ESCO 标准库已在上方标签标注不展示 -->
              <el-tooltip
                v-if="source.source_type !== 'esco'"
                placement="top"
                :show-after="200"
              >
                <template #content>
                  {{ isCrawlableSource(source) ? '立即抓取该平台最新岗位并写入采集库（不执行抽取/入图）' : '该数据源尚未配置爬虫平台，暂不支持立即采集' }}
                </template>
                <el-button
                  size="small"
                  type="warning"
                  plain
                  :disabled="!isCrawlableSource(source) || source.status === 'paused' || source.status === 'inactive'"
                  @click="handleImmediateCrawl(source)"
                >
                  立即采集
                </el-button>
              </el-tooltip>
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

/* 业务说明横幅 — 已迁移到 BusinessBanner.vue */


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
.card-desc {
  margin: 0 0 var(--space-1);
  font-size: var(--font-size-sm);
  line-height: 1.5;
  color: var(--text-tertiary);
}
.card-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
  margin-bottom: var(--space-2);
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


