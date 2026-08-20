<script setup lang="ts">
/**
 * AdminOverview — business-overview tab for the management console.
 *
 * One-screen business map so a new admin user can land here and in
 * <30 seconds understand:
 *  - the four business KPIs the system cares about
 *  - which business stages exist and which tabs answer which question
 *  - where the most pressing action items live
 *
 * The component is intentionally a thin orchestrator: each card reads
 * from a single existing store so the overview never goes stale relative
 * to its underlying data source.
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Grid, Connection, DataLine, Clock, Promotion, DataAnalysis } from '@element-plus/icons-vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useReviewStore } from '@/stores/review'
import AdminFlow from '@/components/AdminFlow.vue'
import request from '@/api/request'

const router = useRouter()
const dashboard = useDashboardStore()
const review = useReviewStore()

// Surface load failures so the user can retry instead of staring at a row of "0" KPIs.
const loadError = ref<string | null>(null)
const loading = ref(false)

// Data health metrics
interface DataHealth {
  total_positions: number
  approved_positions: number
  positions_no_skills: number
  positions_no_skills_pct: number
  positions_unclassified: number
  positions_unclassified_pct: number
  positions_no_name_cn: number
  positions_no_name_cn_pct: number
  total_skills: number
  skills_no_name_cn: number
  skills_no_name_cn_pct: number
  health_status: string
}
const dataHealth = ref<DataHealth | null>(null)

async function refresh() {
  loading.value = true
  loadError.value = null
  const results = await Promise.allSettled([
    dashboard.fetchOverview(),
    review.fetchStats(),
    request.get('/admin/data-health').then((r: any) => { dataHealth.value = r.data }),
  ])
  const failures = results
    .map((r, i) => ({ r, i }))
    .filter(({ r }) => r.status === 'rejected')
  if (failures.length > 0) {
    const names = ['总览数据', '审核统计']
    loadError.value = `部分数据加载失败：${failures.map(f => names[f.i]).join('、')}`
  }
  loading.value = false
}

onMounted(refresh)

const overview = computed(() => dashboard.overview)

const kpiCards = computed(() => {
  const o = overview.value
  return [
    {
      key: 'pending-content',
      label: '待审内容',
      // sum BOTH pending reviews (position + skill) so the card isn't silently dropping one
      value: (review.stats.position_pending_review ?? 0) + (review.stats.skill_pending_review ?? 0),
      suffix: '岗位 / 技能',
      icon: Clock,
      color: '#f59e0b',
      tab: 'content-review',
    },
    {
      key: 'pending-evolution',
      label: '待审演化',
      // read evolution_pending (low-trust EvolutionChangelog entries) instead of skill_pending_review
      value: review.stats.evolution_pending ?? 0,
      suffix: '个低信任变更',
      icon: Promotion,
      color: '#3b82f6',
      tab: 'evolution',
    },
    {
      key: 'weekly-new',
      label: '本周新增节点',
      // backend now uses week_start (Monday), not last-7-days
      value: o?.weekly_new_nodes ?? 0,
      suffix: '个岗位/技能',
      icon: Grid,
      color: '#10b981',
      tab: 'nodes',
    },
    {
      key: 'trust',
      label: '平均信任度',
      // backend reports real Skill.trust_score average from Neo4j
      value: o ? Math.round(o.trust_score * 100) : 0,
      suffix: '%',
      icon: DataLine,
      color: '#6366f1',
      tab: 'quality',
    },
  ]
})

function navigateTo(tab: string) {
  if (tab === 'quality') {
    router.push('/quality')
    return
  }
  // Emit a custom event the Admin page listens for (avoids prop-drilling).
  window.dispatchEvent(new CustomEvent('admin:navigate', { detail: tab }))
}

// Friendly description for the right-hand "what each tab does" card.
const tabCards = [
  {
    key: 'content-review',
    title: '内容审核',
    desc: '审核新发现的岗位和技能。',
    color: 'warning',
  },
  {
    key: 'evolution',
    title: '演化变更',
    desc: '每周自动分析发现的能力变更。',
    color: 'info',
  },
  {
    key: 'nodes',
    title: '图谱与质量',
    desc: '直接管理 Neo4j 节点、查看质量数据。',
    color: 'primary',
  },
  {
    key: 'datasources',
    title: '数据采集',
    desc: '管理爬虫数据源、配置同步策略。',
    color: 'success',
  },
  {
    key: 'prompts',
    title: 'Prompt 工程',
    desc: 'LLM 抽取提示词版本与 A/B 测试。',
    color: 'info',
  },
  {
    key: 'users',
    title: '系统',
    desc: '用户管理、审计日志。',
    color: 'danger',
  },
]
</script>

<template>
  <div class="admin-overview">
    <!-- Surface load failures with a retry button instead of silently rendering all KPIs as 0. -->
    <el-alert
      v-if="loadError"
      type="warning"
      :closable="false"
      show-icon
      class="load-error"
    >
      <template #title>
        {{ loadError }}
      </template>
      <p>系统可能返回了部分数据 — 仍可点击重试刷新。</p>
      <el-button
        size="small"
        type="primary"
        plain
        :loading="loading"
        @click="refresh"
      >
        重试
      </el-button>
    </el-alert>

    <!-- ─── 业务流可视化 ─── -->
    <el-card
      shadow="never"
      class="flow-card"
    >
      <template #header>
        <div class="flow-card-header">
          <Connection class="flow-header-icon" />
          <div>
            <h3 class="flow-title">
              StarMap 业务闭环
            </h3>
            <p class="flow-subtitle">
              JD 文本 → 智能抽取 → 图谱更新 → 人工审核 → 匹配诊断 → 学习路径
            </p>
          </div>
        </div>
      </template>
      <AdminFlow />
    </el-card>

    <!-- ─── 4 个核心 KPI ─── -->
    <div class="kpi-grid">
      <el-card
        v-for="card in kpiCards"
        :key="card.key"
        shadow="hover"
        class="kpi-card"
        :body-style="{ padding: '16px 20px' }"
        @click="navigateTo(card.tab)"
      >
        <div class="kpi-inner">
          <div
            class="kpi-icon"
            :style="{ background: card.color }"
          >
            <el-icon :size="20">
              <component :is="card.icon" />
            </el-icon>
          </div>
          <div class="kpi-text">
            <div class="kpi-value">
              {{ card.value }}
            </div>
            <div class="kpi-label">
              {{ card.label }}
            </div>
            <div class="kpi-suffix">
              {{ card.suffix }}
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- ─── 数据健康度 ─── -->
    <el-card
      v-if="dataHealth"
      shadow="never"
      class="data-health-card"
    >
      <template #header>
        <div class="flow-card-header">
          <DataAnalysis class="flow-header-icon" />
          <div>
            <h3 class="flow-title">
              数据健康度
            </h3>
            <p class="flow-subtitle">
              岗位完整性全览 — 无技能/未分类/无翻译等关键指标
            </p>
          </div>
          <el-tag
            :type="dataHealth.health_status === 'ok' ? 'success' : dataHealth.health_status === 'warn' ? 'warning' : 'danger'"
            size="small"
            effect="dark"
            class="health-badge"
          >
            {{ dataHealth.health_status === 'ok' ? '健康' : dataHealth.health_status === 'warn' ? '需关注' : '需修复' }}
          </el-tag>
        </div>
      </template>
      <el-row :gutter="16">
        <el-col :xs="12" :sm="8" :md="6">
          <div class="health-metric">
            <div class="health-value" :class="{ 'danger': dataHealth.positions_no_skills_pct > 30 }">
              {{ dataHealth.positions_no_skills }}
            </div>
            <div class="health-label">无技能岗位</div>
            <div class="health-pct">{{ dataHealth.positions_no_skills_pct }}%</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="8" :md="6">
          <div class="health-metric">
            <div class="health-value" :class="{ 'danger': dataHealth.positions_unclassified_pct > 30 }">
              {{ dataHealth.positions_unclassified }}
            </div>
            <div class="health-label">未分类行业</div>
            <div class="health-pct">{{ dataHealth.positions_unclassified_pct }}%</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="8" :md="6">
          <div class="health-metric">
            <div class="health-value" :class="{ 'warning': dataHealth.positions_no_name_cn_pct > 50 }">
              {{ dataHealth.positions_no_name_cn }}
            </div>
            <div class="health-label">无中文名</div>
            <div class="health-pct">{{ dataHealth.positions_no_name_cn_pct }}%</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="8" :md="6">
          <div class="health-metric">
            <div class="health-value" :class="{ 'warning': dataHealth.skills_no_name_cn_pct > 50 }">
              {{ dataHealth.skills_no_name_cn }}
            </div>
            <div class="health-label">技能无中文名</div>
            <div class="health-pct">{{ dataHealth.skills_no_name_cn_pct }}%</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- ─── 各 Tab 一句话说明 ─── -->
    <el-card
      shadow="never"
      class="tab-cards"
    >
      <template #header>
        <h3 class="section-title">
          管理后台 6 大功能区
        </h3>
        <p class="section-subtitle">
          点击上方任意 KPI 或下方卡片切换到对应 Tab
        </p>
      </template>
      <el-row :gutter="16">
        <el-col
          v-for="tab in tabCards"
          :key="tab.key"
          :xs="24"
          :sm="12"
          :md="8"
        >
          <el-card
            shadow="hover"
            class="tab-card"
            :body-style="{ padding: '12px 16px' }"
            @click="navigateTo(tab.key)"
          >
            <el-tag
              :type="tab.color"
              size="small"
              effect="dark"
              class="tab-tag"
            >
              {{ tab.title }}
            </el-tag>
            <p class="tab-desc">
              {{ tab.desc }}
            </p>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <!-- ─── 系统健康提示 ─── -->
    <el-alert
      v-if="overview?.stale"
      type="warning"
      :closable="false"
      show-icon
    >
      <template #title>
        系统数据可能过时（自 {{ overview.stale_since ? new Date(overview.stale_since * 1000).toLocaleString() : '未知' }} 起未更新）
      </template>
      某些数据源不可用。当前展示的是缓存值。请检查 数据采集 Tab 中的爬虫状态。
    </el-alert>
  </div>
</template>

<style scoped>
.admin-overview {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.load-error {
  border-radius: var(--radius-lg);
}
.load-error :deep(p) {
  margin: 4px 0 8px;
  font-size: var(--font-size-sm);
  color: var(--foreground);
}

.flow-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.flow-header-icon {
  /* E1 fix: SVG defaults to 100% width/height if not constrained — it
     was filling the entire flex container (475×475). Pin to 24×24 to
     match the icon's intended size next to the title text. */
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  font-size: 24px;
  color: var(--primary);
}
.flow-title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 700;
  color: var(--foreground);
}
.flow-subtitle {
  margin: 2px 0 0;
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}
@media (max-width: 992px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 576px) {
  .kpi-grid { grid-template-columns: 1fr; }
}

.kpi-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.kpi-card:hover {
  transform: translateY(-2px);
}

.kpi-inner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.kpi-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.kpi-text {
  flex: 1;
  min-width: 0;
}

.kpi-value {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  line-height: 1.1;
  color: var(--foreground);
  font-variant-numeric: tabular-nums;
}
.kpi-label {
  font-size: var(--font-size-sm);
  color: var(--foreground);
  font-weight: 500;
  margin-top: 2px;
}
.kpi-suffix {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

.section-title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 700;
  color: var(--foreground);
}
.section-subtitle {
  margin: 4px 0 0;
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
}

.tab-card {
  cursor: pointer;
  margin-bottom: var(--space-4);
  transition: border-color 0.2s, transform 0.2s;
}
.tab-card:hover {
  border-color: var(--primary);
  transform: translateY(-1px);
}
.tab-tag {
  margin-bottom: 6px;
}
.tab-desc {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  line-height: 1.5;
}

/* Data Health Card */
.data-health-card {
  border: 1px solid var(--border);
}
.health-badge {
  margin-left: auto;
}
.health-metric {
  text-align: center;
  padding: var(--space-3);
}
.health-value {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  color: var(--foreground);
  font-variant-numeric: tabular-nums;
}
.health-value.danger {
  color: var(--destructive);
}
.health-value.warning {
  color: #f59e0b;
}
.health-label {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin-top: 2px;
}
.health-pct {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  margin-top: 1px;
}
</style>