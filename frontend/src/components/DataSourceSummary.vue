<script setup lang="ts">
/**
 * DataSourceSummary — 数据源 KPI 汇总行
 * 从 DataSources.vue 拆出，展示总数/记录量/质量分/异常数
 */
import { computed } from 'vue'
import { Connection, Coin, DataLine, WarningFilled } from '@element-plus/icons-vue'
import { chartColors } from '@/utils/chartTheme'
import { formatRecords } from '@/composables/useDataSourceCharts'
import type { DataSourceDetail } from '@/types/datasource'

const props = defineProps<{
  sources: DataSourceDetail[]
  loading: boolean
}>()

const cc = chartColors()

const stats = computed(() => {
  const src = props.sources.filter((s) => s.status !== 'inactive')
  const evaluated = src.filter((s) => s.avg_quality_score > 0)
  const avgQuality = evaluated.length
    ? evaluated.reduce((sum, s) => sum + s.avg_quality_score, 0) / evaluated.length
    : null
  return {
    total: src.length,
    active: src.filter((s) => s.status === 'active').length,
    error: src.filter((s) => s.status === 'error').length,
    evaluatedCount: evaluated.length,
    totalRecords: src.reduce((sum, s) => sum + s.total_records, 0),
    avgQuality,
  }
})
</script>

<template>
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
              {{ stats.total }}
            </div>
            <div class="kpi-sub">
              {{ stats.active }} 个活跃
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
              {{ formatRecords(stats.totalRecords) }}
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
              :style="{ color: stats.avgQuality === null ? cc.info : (stats.avgQuality >= 0.8 ? cc.success : cc.warning) }"
            >
              {{ stats.avgQuality === null ? '未评估' : `${(stats.avgQuality * 100).toFixed(1)}%` }}
            </div>
            <div class="kpi-sub">
              <template v-if="stats.avgQuality !== null">
                <span :class="stats.avgQuality >= 0.8 ? 'trend-up' : 'trend-down'">
                  {{ stats.avgQuality >= 0.8 ? '▲' : '▼' }}
                </span>
                {{ stats.avgQuality >= 0.8 ? '质量优秀' : '有提升空间' }}
                <span v-if="stats.evaluatedCount < stats.total">（{{ stats.evaluatedCount }}/{{ stats.total }} 已评估）</span>
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
              :style="{ color: stats.error > 0 ? cc.danger : cc.success }"
            >
              {{ stats.error }}
            </div>
            <div class="kpi-sub">
              {{ stats.error > 0 ? '需关注' : '全部正常' }}
            </div>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<style scoped>
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
.kpi-body { flex: 1; min-width: 0; }
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
.trend-up { color: var(--success); font-weight: 600; }
.trend-down { color: var(--destructive); font-weight: 600; }
.mb-4 { margin-bottom: var(--space-4); }
@media (max-width: 768px) {
  .kpi-value { font-size: var(--font-size-2xl); }
}
</style>
