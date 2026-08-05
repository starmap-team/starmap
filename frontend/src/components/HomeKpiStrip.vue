<script setup lang="ts">
import { Collection, DataAnalysis, Upload, Document, TrendCharts, Connection } from "@element-plus/icons-vue"

defineProps<{
  totalDomains: number
  totalPositions: number
  totalSkills: number
  // M6：关系边 KPI 统一用 REQUIRES 总数（=大屏/Neo4j/PG 口径），不随视图模式变化，避免跨页面“同名异值”
  totalRelations: number
  // 动态分组维度标签（随 overviewMode 切换：技术领域/技术栈/职级分组）
  groupLabel?: string
  groupTrend?: string
}>()

const emit = defineEmits<{
  navigate: [path: string]
}>()

// M5/M6：每个 KPI 数字的口径说明，避免跨页面“同名异值”误导
function kpiTooltip(field: string): string {
  const map: Record<string, string> = {
    totalDomains: '知识图谱核心分类数（domain）。',
    totalPositions: '图谱 Position 节点数，与 PostgreSQL position_records 同步（单一真理源，可在 管理后台/数据源诊断 核对）。',
    totalSkills: '图谱 Skill 节点数（去重）。',
    totalRelations: '岗位-技能 REQUIRES 关系边总数（与数据大屏口径一致，=Neo4j/PG）。领域视图中的连线是按领域聚合后的跨领域连接，数量较少，故与该 KPI 不同。',
  }
  return map[field] ?? ''
}
</script>

<template>
  <div class="kpi-strip stagger">
    <div class="kpi-card">
      <div class="kpi-icon kpi-icon--info">
        <el-icon><DataAnalysis /></el-icon>
      </div>
      <div class="kpi-body">
        <span class="kpi-label">{{ groupLabel || '技术领域' }}</span>
        <span class="kpi-value">{{ totalDomains }}</span>
        <span class="kpi-trend">{{ groupTrend || '知识图谱核心分类' }}</span>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon kpi-icon--primary">
        <el-icon><Collection /></el-icon>
      </div>
      <div class="kpi-body">
        <span class="kpi-label">岗位数</span>
        <span class="kpi-value">{{ totalPositions }}</span>
        <span
          class="kpi-trend"
          :title="kpiTooltip('totalPositions')"
        >图谱节点（含历史）</span>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon kpi-icon--success">
        <el-icon><TrendCharts /></el-icon>
      </div>
      <div class="kpi-body">
        <span class="kpi-label">技能数</span>
        <span class="kpi-value">{{ totalSkills }}</span>
        <span
          class="kpi-trend"
          :title="kpiTooltip('totalSkills')"
        >图谱快照节点数</span>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon kpi-icon--warning">
        <el-icon><Connection /></el-icon>
      </div>
      <div class="kpi-body">
        <span class="kpi-label">关系边</span>
        <span class="kpi-value">{{ totalRelations }}</span>
        <span
          class="kpi-trend"
          :title="kpiTooltip('totalRelations')"
        >岗位-技能关系</span>
      </div>
    </div>
    <div class="kpi-actions">
      <el-button
        size="small"
        :icon="Upload"
        @click="emit('navigate', '/match')"
      >
        简历匹配
      </el-button>
      <el-button
        size="small"
        :icon="Document"
        @click="emit('navigate', '/extract')"
      >
        JD 抽取
      </el-button>
      <el-button
        size="small"
        :icon="TrendCharts"
        @click="emit('navigate', '/evolution')"
      >
        演化趋势
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.kpi-strip { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.kpi-card { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-5); background: var(--card); border: 1px solid var(--border); border-radius: var(--radius-xl); min-width: 140px; transition: all var(--duration-normal) var(--ease-out); position: relative; overflow: hidden; }
.kpi-card::before { content: ''; position: absolute; inset: 0; opacity: 0; background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 4%, transparent), transparent); transition: opacity var(--duration-normal); }
.kpi-card:hover { border-color: color-mix(in srgb, var(--primary) 20%, var(--border)); box-shadow: var(--shadow-md); transform: translateY(-2px); }
.kpi-card:hover::before { opacity: 1; }
.kpi-icon { width: 38px; height: 38px; border-radius: var(--radius-lg); display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: var(--font-size-xl); position: relative; z-index: 1; }
.kpi-body { display: flex; flex-direction: column; position: relative; z-index: 1; }
.kpi-value { font-size: var(--font-size-2xl); font-weight: 800; color: var(--foreground); line-height: 1.1; letter-spacing: var(--tracking-tight); font-variant-numeric: tabular-nums; }
.kpi-label { font-size: 10px; color: var(--muted-foreground); letter-spacing: 0.06em; text-transform: uppercase; font-weight: 600; }
.kpi-trend { font-size: var(--font-size-xs); color: var(--muted-foreground); margin-top: 1px; opacity: 0.7; }
.kpi-actions { display: flex; gap: var(--space-2); margin-left: auto; }
.kpi-icon--info { background: var(--info-ghost); color: var(--info); }
.kpi-icon--primary { background: var(--primary-ghost); color: var(--primary); }
.kpi-icon--success { background: var(--success-ghost); color: var(--success); }
.kpi-icon--warning { background: var(--warning-ghost); color: var(--warning); }

@media (max-width: 1024px) {
  .kpi-actions { margin-left: 0; width: 100%; }
}
@media (max-width: 768px) {
  .kpi-strip { flex-direction: column; align-items: stretch; }
  .kpi-actions { flex-direction: column; }
}
</style>
