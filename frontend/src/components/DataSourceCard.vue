<script setup lang="ts">
/**
 * DataSourceCard — 单个数据源卡片
 * 从 DataSources.vue 拆出，含权威度仪表盘、统计、操作按钮
 */
import { computed } from 'vue'
import { RefreshRight, Upload } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { asTagType } from '@/utils/element'
import { chartColors } from '@/utils/chartTheme'
import {
  getAuthorityGaugeOption,
  getStatusBadge,
  getSourceTypeLabel,
  formatLastCrawl,
  formatRecords,
  getSourceNameLabel,
} from '@/composables/useDataSourceCharts'
import { SOURCE_DESCRIPTIONS, isCrawlableSource } from '@/constants/labels'
import type { DataSourceDetail } from '@/types/datasource'

use([GaugeChart, TooltipComponent])

const cc = chartColors()

const props = defineProps<{
  source: DataSourceDetail
  syncing: boolean
}>()

const emit = defineEmits<{
  sync: []
  crawl: []
  'manual-import': []
  activate: []
}>()

const statusBadge = computed(() => {
  if (props.source.status === 'active' && props.source.has_adapter === false) {
    return { type: 'warning' as const, label: '未配置' }
  }
  return getStatusBadge(props.source.status)
})

function formatQuality(s: DataSourceDetail): string {
  if (s.total_records === 0) return '未评估'
  if (s.avg_quality_score > 0) return `${(s.avg_quality_score * 100).toFixed(0)}%`
  return '未评估'
}

function qualityColor(s: DataSourceDetail) {
  if (s.avg_quality_score > 0) return s.avg_quality_score >= 0.8 ? cc.success : cc.warning
  return cc.info
}
</script>

<template>
  <el-card
    shadow="hover"
    class="source-card"
  >
    <!-- 卡片头部 -->
    <div class="card-header">
      <div class="card-title-group">
        <span class="card-name">{{ getSourceNameLabel(source.name) }}</span>
        <el-tag
          :type="asTagType(statusBadge.type)"
          size="small"
          effect="light"
          round
        >
          {{ statusBadge.label }}
        </el-tag>
        <!-- 2026-08-20 (debug 修复): 未配置源引导说明 —— 用户不知道"未配置"有何用处 -->
        <el-tooltip
          v-if="source.status === 'active' && source.has_adapter === false && source.source_type === 'crawler'"
          placement="top"
          :show-after="200"
        >
          <template #content>
            该源为预留数据源，尚未配置爬虫适配器（platform），当前无法采集。
            如需启用：在 crawler/spiders/ 实现适配器并在 spider_registry.py 注册后，
            配置 platform 即可参与自动采集。也可改用手动导入补充数据。
          </template>
          <span class="unconfigured-hint">预留 · 待配置适配器后可用</span>
        </el-tooltip>
      </div>
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
        <el-tag
          v-if="source.source_type === 'esco'"
          size="small"
          type="info"
          effect="plain"
          round
        >
          标准库 · 无需采集
        </el-tag>
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
        <el-tag
          v-if="source.total_records === 0 && !source.last_crawl_at"
          size="small"
          type="warning"
          effect="plain"
          round
          title="该数据源尚未执行过采集，下方记录/质量数值为 0 属正常空态"
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

    <!-- 权威度环形图 + 统计 -->
    <div class="card-body">
      <div class="card-gauge">
        <VChart
          :option="getAuthorityGaugeOption(source.authority_score)"
          style="width: 130px; height: 110px;"
          autoresize
        />
      </div>
      <div class="card-stats">
        <!-- 2026-08-20 (debug 修复): 全部指标加 tooltip 说明，让用户知根知底 -->
        <div class="stat-row">
          <span class="stat-label">数据质量</span>
          <el-tooltip
            placement="top"
            :show-after="200"
          >
            <template #content>
              数据质量 = 已抽取(有效) / (已抽取 + 重复)。反映该源采集数据的可用性：
              越高说明采集的职位大部分有效且不重复。未评估 = 尚无抽取数据。
            </template>
            <span
              class="stat-value stat-link"
              :style="{ color: qualityColor(source) }"
            >{{ formatQuality(source) }}</span>
          </el-tooltip>
        </div>
        <div class="stat-row">
          <span class="stat-label">记录总量</span>
          <el-tooltip
            placement="top"
            :show-after="200"
          >
            <template #content>
              该源累计采集入库的记录总数（含待抽取/已抽取/重复），来自原始岗位数据按源统计。
            </template>
            <span class="stat-value stat-link">{{ formatRecords(source.total_records) }}</span>
          </el-tooltip>
        </div>
        <div class="stat-row">
          <span class="stat-label">有效记录</span>
          <el-tooltip
            placement="top"
            :show-after="200"
          >
            <template #content>
              已成功通过智能抽取的记录数 = 真正进入岗位/技能体系的职位数。
              记录总量高但有效记录低 = 多数还在抽取队列或重复。
            </template>
            <span class="stat-value stat-link">{{ source.valid_records.toLocaleString() }}</span>
          </el-tooltip>
        </div>
        <div class="stat-row">
          <span class="stat-label">重复率</span>
          <el-tooltip
            placement="top"
            :show-after="200"
          >
            <template #content>
              重复记录占比 = 重复 / (有效 + 重复)。重复通常因平台重复返回或多次采集相同职位；
              重复率高的源采集效率低，但不影响已入库数据。
            </template>
            <span
              class="stat-value stat-link"
              :style="{ color: source.duplicate_rate > 0.2 ? cc.danger : cc.success }"
            >{{ (source.duplicate_rate * 100).toFixed(1) }}%</span>
          </el-tooltip>
        </div>
      </div>
    </div>

    <!-- 底部：同步时间 + 操作按钮 -->
    <div class="card-footer">
      <span class="sync-time">
        {{ source.total_records > 0 ? '最后同步' : '最近尝试' }}：{{ formatLastCrawl(source.last_crawl_at) }}
      </span>
      <div class="card-actions">
        <el-tooltip
          placement="top"
          :show-after="200"
        >
          <template #content>
            触发该数据源完整流水线：爬取 → 去重 → 清洗 → 技能抽取 → 写入图谱（通常 30-90 秒）
          </template>
          <el-button
            size="small"
            type="primary"
            :loading="syncing"
            :disabled="!source.has_adapter || source.status === 'paused' || source.status === 'inactive'"
            @click="emit('sync')"
          >
            <el-icon
              v-if="!syncing"
              class="el-icon--left"
            >
              <RefreshRight />
            </el-icon>
            {{ syncing ? '同步中...' : '一键同步' }}
          </el-button>
        </el-tooltip>
        <el-button
          v-if="source.source_type === 'manual'"
          size="small"
          type="success"
          plain
          @click="emit('manual-import')"
        >
          <el-icon class="el-icon--left">
            <Upload />
          </el-icon>
          手动导入
        </el-button>
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
            @click="emit('crawl')"
          >
            立即采集
          </el-button>
        </el-tooltip>
        <!-- 2026-08-20: paused 源恢复入口（此前只在 Admin 页，数据源页无法恢复） -->
        <el-tooltip
          v-if="source.status === 'paused'"
          placement="top"
          :show-after="200"
        >
          <template #content>
            该数据源因质量/权威分被自动暂停。恢复后立即进入采集调度（已自动修复"无历史数据源不暂停"逻辑，恢复后不会再被误停）
          </template>
          <el-button
            size="small"
            type="success"
            plain
            @click="emit('activate')"
          >
            恢复
          </el-button>
        </el-tooltip>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
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
.stat-link {
  cursor: help;
  border-bottom: 1px dashed var(--border);
}
.unconfigured-hint {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  background: var(--muted);
  padding: 2px 8px;
  border-radius: 999px;
  cursor: help;
}
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
.card-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
@media (max-width: 768px) {
  .card-body { flex-direction: column; text-align: center; }
  .card-stats { width: 100%; }
}
</style>
