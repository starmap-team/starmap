<script setup lang="ts">
import { Collection, DataAnalysis, Upload, Document, TrendCharts, Connection } from "@element-plus/icons-vue"

defineProps<{
  totalDomains: number
  totalPositions: number
  totalSkills: number
  totalRelations: number
}>()

const emit = defineEmits<{
  navigate: [path: string]
}>()
</script>

<template>
  <div class="kpi-strip stagger">
    <div class="kpi-card">
      <div class="kpi-icon kpi-icon--info">
        <el-icon><DataAnalysis /></el-icon>
      </div>
      <div class="kpi-body">
        <span class="kpi-label">技术领域</span>
        <span class="kpi-value">{{ totalDomains }}</span>
        <span class="kpi-trend">知识图谱核心分类</span>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon kpi-icon--primary">
        <el-icon><Collection /></el-icon>
      </div>
      <div class="kpi-body">
        <span class="kpi-label">岗位数</span>
        <span class="kpi-value">{{ totalPositions }}</span>
        <span class="kpi-trend">IT 行业全覆盖</span>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon kpi-icon--success">
        <el-icon><TrendCharts /></el-icon>
      </div>
      <div class="kpi-body">
        <span class="kpi-label">技能数</span>
        <span class="kpi-value">{{ totalSkills }}</span>
        <span class="kpi-trend">持续增长中</span>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon kpi-icon--warning">
        <el-icon><Connection /></el-icon>
      </div>
      <div class="kpi-body">
        <span class="kpi-label">关系数</span>
        <span class="kpi-value">{{ totalRelations }}</span>
        <span class="kpi-trend">知识关联网络</span>
      </div>
    </div>
    <div class="kpi-actions">
      <el-button size="small" :icon="Upload" @click="emit('navigate', '/match')">简历匹配</el-button>
      <el-button size="small" :icon="Document" @click="emit('navigate', '/extract')">JD 抽取</el-button>
      <el-button size="small" :icon="TrendCharts" @click="emit('navigate', '/evolution')">演化趋势</el-button>
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
