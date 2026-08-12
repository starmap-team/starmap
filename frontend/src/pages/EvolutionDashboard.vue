<script setup lang="ts">
/**
 * 演化看板页 — CII 时序曲线（技能需求通胀指数）
 * Task 3 增强: 技能趋势时间线、新兴技能卡片、CII仪表盘、技能对比
 */
import { ref, onMounted, computed } from 'vue'
import { use } from 'echarts/core'
import { LineChart, BarChart, GaugeChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import MainLayout from '@/layouts/MainLayout.vue'
import { useEvolutionStore } from '@/stores/evolution'
import type { TrendItem, EmergingAlert } from '@/stores/evolution'
import { useEvolutionCharts, useEvolutionActions, formatChange, TREND_LABEL, TREND_TAG_TYPE } from '@/composables/useEvolutionDashboard'
// ponytail: alias uppercase constants to camelCase for template binding without renaming template
const trendLabel = TREND_LABEL
const trendTagType = TREND_TAG_TYPE
import EvolutionChangelogDrawer from '@/components/EvolutionChangelogDrawer.vue'
import EmptyState from '@/components/EmptyState.vue'
import BusinessBanner from '@/components/BusinessBanner.vue'

use([CanvasRenderer, LineChart, BarChart, GaugeChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const evo = useEvolutionStore()

// Aliases for template binding (store-backed)
const items = computed(() => evo.trendItems)
const snapshots = computed(() => evo.snapshots)
const snapshotsLoading = computed(() => evo.snapshotsLoading)
const changelogData = computed(() => evo.changelogData)
const changelogLoading = computed(() => evo.changelogLoading)
const loading = computed(() => evo.loading)
const sliderMarks = computed<Record<number, string>>(() => {
  const marks: Record<number, string> = {}
  const step = Math.max(1, Math.floor(snapshots.value.length / 6))
  snapshots.value.forEach((s, i) => {
    if (i % step === 0 || i === snapshots.value.length - 1) {
      marks[i] = s.snapshot_date.slice(0, 7)
    }
  })
  return marks
})

const selectedSkill = ref('')

// 技能对比
const compareSkillA = ref('')
const compareSkillB = ref('')

// Chart options — extracted to composable
const { chartOption, ciiGaugeOption, compareOption } = useEvolutionCharts(
  items, selectedSkill, compareSkillA, compareSkillB,
)

// C1: 新兴技能卡片渲染 items 中 rising/emerging 子集（原误把 ECharts option 当列表迭代）
// E4: 改与下方「新兴技能预警」表同源 —— 用 /evolution/emerging-alerts 的 emerging+rising，
//     避免与预警表/涌现数 KPI 三个数据源各说各话
const emergingItems = computed<EmergingAlert[]>(() =>
  evo.emergingAlerts.filter(a => a.level === 'emerging' || a.level === 'rising')
)

// E5: 预警表级别中文化 + 颜色映射（emerging=涌现/rising=上升/declining=下降/stable=平稳）
const ALERT_LEVEL_LABEL: Record<string, string> = {
  emerging: '涌现', rising: '上升', declining: '下降', stable: '平稳',
}
const ALERT_LEVEL_TAG: Record<string, string> = {
  emerging: 'danger', rising: 'warning', declining: 'info', stable: 'success',
}

// Drawer / fetch handlers / snapshot state (extracted — Phase 7 D round 8)
const {
  drawerVisible,
  evidenceDrawerOpen,
  selectedSkillForDetail,
  snapshotIndex,
  selectedSnapshotDate,
  fetchTrends,
  fetchSnapshots,
  fetchChangelog,
  onSnapshotChange,
  refresh,
} = useEvolutionActions(evo)

// 10-03 (D-12): 空态引导 — 触发演化分析（Celery 异步，已排队反馈，无 SSE）
const analyzing = ref(false)
async function triggerAnalyze() {
  if (analyzing.value) return
  analyzing.value = true
  try {
    const res = await evo.analyze(evo.kpi?.days ?? 90)
    const queued = res?.message === 'queued' || Boolean(res?.task_id)
    ElMessage.success(queued
      ? `演化分析已排队（任务 ${String(res?.task_id ?? '').slice(0, 8)}...，窗口 ${res?.days ?? 90} 天）`
      : '演化分析已触发，请稍后刷新查看结果')
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail ?? '触发演化分析失败')
  } finally {
    analyzing.value = false
  }
}

// KPI 卡格式化 — E2: 每项带口径拆解行（用户可感知数值从何而来）
const kpiCards = computed(() => [
  { label: '涌现技能数', value: evo.kpi.emerging_count, unit: '', tip: 'emerging + rising 技能数（Z-score 检测，全量时序）', breakdown: `= ${evo.emergingAlerts.filter(a => a.level === 'emerging').length} 涌现 + ${evo.emergingAlerts.filter(a => a.level === 'rising').length} 上升 · 与下方预警表同源` },
  { label: '信任均值', value: `${Math.round((evo.kpi.trust_mean ?? 0) * 100)}%`, unit: '', tip: '变更日志 trust_score 真实均值', breakdown: `evolution_changelog 全部记录 avg(trust_score)；对照：/quality 平均信任度 ${Math.round((evo.kpi.trust_mean_neo4j_skill ?? 0) * 100)}%（Neo4j Skill.trust_score 实时均值）` },
  { label: 'CII 均值', value: evo.kpi.cii_mean, unit: '', tip: '技能 CII 时序末点均值（基准 100，近 90 天窗口）', breakdown: `${items.value.length} 项技能 CII 末点算术平均` },
  { label: '预警数', value: evo.kpi.alert_count, unit: '', tip: 'emerging/rising/declining 非平稳信号数', breakdown: `=${evo.emergingAlerts.filter(a => a.level === 'emerging').length} 涌现 + ${evo.emergingAlerts.filter(a => a.level === 'rising').length} 上升 + ${evo.emergingAlerts.filter(a => a.level === 'declining').length} 下降` },
])

// E2/E7: 全局数据口径说明 —— 让用户能感知每个数值的计算依据与数据来源
const dataSourceExplainer = computed(() => [
  { metric: '涌现技能数 / 新兴技能 / 预警数', source: 'GET /evolution/emerging-alerts · skill_timeseries（全量时序）', formula: 'Z-score 检测：z>2.0 且频次≥3 且源≥3 → 涌现(emerging)；z>1.5 → 上升(rising)；z<-1.5 → 下降(declining)' },
  { metric: 'CII（能力通胀指数）', source: 'GET /evolution/trends · skill_timeseries（近 90 天窗口）', formula: '基准 100 = 频次前半段均值；CII = 当期频次 ÷ 基准 × 100（>100 表示需求膨胀）' },
  { metric: '变化', source: '同 /evolution/trends', formula: 'CII 末点相对基准 100 的涨跌幅 %' },
  { metric: '置信度', source: '同 /evolution/trends', formula: 'clamp(0.5 + z_score/10, 0, 1) — 由 Z-score 映射的检测置信度' },
  { metric: '信任均值', source: 'GET /evolution/kpi · evolution_changelog', formula: '全部变更记录 trust_score 的算术平均（0~1）' },
  { metric: 'Z-score', source: '同上', formula: '当前频次相对历史均值的标准差倍数，|z| 越大信号越强' },
  { metric: '可迁移性', source: '同 /evolution/emerging-alerts', formula: '技能跨领域岗位覆盖比例（EmergenceFinder.portability_score）' },
  { metric: '快照时间线', source: 'GET /evolution/snapshots · evolution_snapshots', formula: '每次演化分析生成的岗位能力快照；选择快照查看该岗位对应 CII 历史' },
])

// E1: 快照滑块当前选中的快照（联动次区展示岗位技能清单 + CII 历史）
const selectedSnapshot = computed(() => {
  const snap = snapshots.value[snapshotIndex.value]
  return snap ?? null
})
const snapshotCiiHistory = computed(() => evo.ciiHistory)

// E1-2: 快照时间仅显示日期（去掉 00:00:00 等无意义时间部分）
function formatSnapshotDate(date?: string): string {
  if (!date) return ''
  return date.slice(0, 10)
}

// E1-2: 当前快照的技能清单（string 或 {name} 对象统一取显示名）
const snapshotSkills = computed<unknown[]>(() => {
  const snap = selectedSnapshot.value
  if (!snap) return []
  return [...(snap.required_skills ?? []), ...(snap.preferred_skills ?? [])]
})

// E1: 快照技能条目可能是 string 或 {name} 对象，统一取显示名（模板内不做 TS 强转）
function skillDisplayName(skill: unknown): string {
  if (typeof skill === 'string') return skill
  if (skill && typeof skill === 'object' && 'name' in skill) {
    const name = (skill as { name?: unknown }).name
    return typeof name === 'string' ? name : ''
  }
  return ''
}

// 10-03 (D-11): 次区 — 演化路径/CII 历史/迁移性，数据源全部复用已有 store 数据，
// 不得造前端估算数据（RESEARCH §3 D-11）。
const trackedPositions = computed<string[]>(() =>
  [...new Set(snapshots.value.map(s => s.position_name).filter(Boolean))]
)
// 未选快照时的默认 CII 列表（趋势概览末点）；选中快照后由 snapshotCiiHistory 替换（E1）
const ciiOverviewList = computed(() =>
  items.value.map(i => ({ skill_name: i.skill_name, last: i.points?.length ? i.points[i.points.length - 1] : 100 }))
)
const portabilityAlerts = computed(() =>
  evo.emergingAlerts.filter(a => a.portability_score != null)
)

onMounted(() => {
  void fetchTrends()
  void fetchSnapshots()
  void evo.fetchEmergingAlerts()  // LOOP-06: fetch alerts on mount
  void evo.fetchKpi()  // 10-03 (D-11): KPI 行数据
})
</script>

<template>
  <MainLayout>
    <div class="evolution-page animate-fade-in">
      <BusinessBanner
        type="warning"
        title="演化分析 + 能力通胀指数 (CII)"
        description="本看板展示岗位技能图谱的演化趋势：新兴技能涌现（Z-score 检测）、技能变更日志、以及 CII 通胀指数（基准 100 = 2024-Q1，反映企业技能要求膨胀程度）。"
        meta="后端: <code>/evolution/*</code> · 数据源: <code>evolution_changelog</code> + <code>skill_timeseries</code> · §7.1 信任度驱动"
      />

      <!-- E2/E7: 数据口径说明 — 让用户可感知每个数值的计算依据与来源 -->
      <el-card
        class="explainer-card"
        shadow="never"
      >
        <el-collapse>
          <el-collapse-item
            title="📐 数据口径说明 — 每个数值怎么算的、来自哪里"
            name="explainer"
          >
            <el-table
              :data="dataSourceExplainer"
              size="small"
              stripe
            >
              <el-table-column
                prop="metric"
                label="指标"
                width="220"
              />
              <el-table-column
                prop="source"
                label="数据来源"
                width="260"
              />
              <el-table-column
                prop="formula"
                label="计算口径"
              />
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <!-- 标题 -->
      <div class="page-header">
        <div>
          <h2 class="page-title">
            演化趋势看板
          </h2>
          <p class="page-subtitle">
            CII 时序曲线 — 技能需求通胀指数（基准 100 = 2024-Q1）
          </p>
        </div>
        <div class="header-actions">
          <el-select
            v-model="selectedSkill"
            placeholder="全部技能"
            clearable
            size="small"
            class="select-sm"
          >
            <el-option
              v-for="item in items"
              :key="item.skill_name"
              :label="item.skill_name"
              :value="item.skill_name"
            />
          </el-select>
          <!-- 10-03 (D-13): 手动刷新按钮 — 无 SSE/轮询 -->
          <el-button
            size="small"
            @click="refresh"
          >
            刷新
          </el-button>
        </div>
      </div>

      <!-- EVOLVE-FE-04/D-10: 快照时间线滑块 -->
      <el-card
        v-if="snapshots.length"
        class="timeline-card"
        shadow="hover"
      >
        <template #header>
          <div class="card-header-row">
            <span>快照时间线</span>
            <el-tag
              v-if="selectedSnapshotDate"
              size="small"
              effect="plain"
              type="primary"
              class="ml-2"
            >
              {{ formatSnapshotDate(selectedSnapshotDate) }}
            </el-tag>
          </div>
        </template>
        <div class="timeline-row">
          <span class="timeline-label">快照</span>
          <el-slider
            v-model="snapshotIndex"
            :min="0"
            :max="Math.max(0, snapshots.length - 1)"
            :marks="sliderMarks"
            :show-tooltip="true"
            :format-tooltip="(idx: number) => formatSnapshotDate(snapshots[idx]?.snapshot_date ?? '')"
            class="timeline-slider"
            @change="onSnapshotChange"
          />
          <span class="timeline-current">{{ formatSnapshotDate(selectedSnapshotDate) || '—' }}</span>
        </div>
        <!-- E1-2: 切换快照后详情即时显示在交互处（不再藏到页面底部），并说明其用途 -->
        <div
          v-if="selectedSnapshot"
          class="snapshot-inline"
        >
          <div class="snapshot-inline-head">
            <el-tag
              size="small"
              type="primary"
              effect="plain"
            >
              当前快照
            </el-tag>
            <span class="snapshot-inline-title">{{ selectedSnapshot.position_name }}</span>
            <span class="snapshot-inline-date">{{ formatSnapshotDate(selectedSnapshot.snapshot_date) }}</span>
          </div>
          <div class="snapshot-skill-chips">
            <template v-if="snapshotSkills.length">
              <el-tag
                v-for="(skill, index) in snapshotSkills"
                :key="skillDisplayName(skill) || index"
                size="small"
                effect="plain"
                class="related-tag"
              >
                {{ skillDisplayName(skill) }}
              </el-tag>
            </template>
            <span
              v-else
              class="snapshot-meta"
            >该快照暂无技能要求</span>
          </div>
          <p class="snapshot-meta">
            数据源: 演化快照（source_count={{ selectedSnapshot.source_count }}）· 拖动滑块查看不同岗位当时的技能要求
            <template v-if="snapshotCiiHistory.length">
              · CII 历史: {{ snapshotCiiHistory.slice(-5).map(h => `${formatSnapshotDate(h.snapshot_date)}=${h.cii}`).join(' → ') }}
            </template>
          </p>
        </div>
      </el-card>
      <el-card
        v-else-if="!snapshotsLoading"
        class="timeline-card"
        shadow="never"
      >
        <EmptyState
          title="暂无快照数据"
          description="演化快照生成后将显示时间线滑块"
        >
          <!-- 10-03 (D-12): 诚实空态 + 引导按钮 -->
          <el-button
            size="small"
            type="primary"
            :loading="analyzing"
            @click="triggerAnalyze"
          >
            触发演化分析
          </el-button>
          <a
            class="guide-doc-link"
            href="docs/design/星图StarMap-项目设计文档（含配图）v3.0.docx"
            target="_blank"
            rel="noopener"
          >
            查看文档
          </a>
        </EmptyState>
      </el-card>

      <!-- 10-03 (D-11): KPI 数字行 — 涌现数/信任均值/CII 均值/预警数 -->
      <div
        v-loading="evo.kpiLoading"
        class="kpi-number-row"
      >
        <el-card
          v-for="card in kpiCards"
          :key="card.label"
          class="kpi-number-card"
          shadow="hover"
        >
          <div
            class="kpi-number-label"
            :title="card.tip"
          >
            {{ card.label }}
          </div>
          <div class="kpi-number-value">
            {{ card.value }}
          </div>
          <!-- E2: 口径拆解行 — 数值从何而来可见 -->
          <div
            class="kpi-number-breakdown"
            :title="card.tip"
          >
            {{ card.breakdown }}
          </div>
        </el-card>
      </div>

      <!-- KPI 区域: CII 仪表盘 + 新兴技能卡片 -->
      <div class="kpi-row">
        <!-- CII 仪表盘 -->
        <el-card
          class="gauge-card"
          shadow="hover"
        >
          <template #header>
            <div class="card-header-row">
              <span>CII 仪表盘</span><span class="card-header-badge">实时</span>
            </div>
          </template>
          <VChart
            v-if="items.length"
            :option="ciiGaugeOption"
            autoresize
            class="chart-h-gauge"
          />
          <EmptyState
            v-else
            title="图表数据为空"
            description="技能 CII 数据将在分析完成后展示"
          />
          <!-- E3: 全部技能模式下展示聚合均值（不再空白）；选择具体技能查看其 CII -->
          <p
            v-if="items.length"
            class="gauge-note"
          >
            {{ selectedSkill ? `当前展示「${selectedSkill}」的 CII` : `未选择技能时展示全部 ${items.length} 项技能的 CII 末点均值` }}
          </p>
        </el-card>

        <!-- 新兴技能卡片 -->
        <el-card
          class="emerging-card"
          shadow="hover"
        >
          <template #header>
            <div class="card-header-row">
              <span>新兴技能</span><el-tag
                type="success"
                size="small"
                effect="plain"
                class="ml-2"
              >
                Z-score 检测
              </el-tag>
            </div>
          </template>
          <!-- E4: 与下方「新兴技能预警」表同源（emerging+rising），消除口径分叉 -->
          <div class="emerging-grid">
            <template v-if="emergingItems.length">
              <div
                v-for="skill in emergingItems"
                :key="skill.skill_name"
                class="emerging-item"
                :title="skill.alert_message"
                @click="fetchChangelog(skill.skill_name)"
              >
                <div class="emerging-name">
                  {{ skill.skill_name }}
                </div>
                <div class="emerging-meta">
                  <el-tag
                    size="small"
                    :type="skill.level === 'emerging' ? 'danger' : 'warning'"
                    effect="light"
                  >
                    {{ ALERT_LEVEL_LABEL[skill.level] ?? skill.level }}
                  </el-tag>
                  <span class="emerging-z">Z {{ skill.z_score.toFixed(1) }}</span>
                  <el-tag
                    size="small"
                    type="success"
                    effect="plain"
                    class="pulse-tag"
                  >
                    ↑
                  </el-tag>
                </div>
              </div>
            </template>
            <EmptyState
              v-else
              title="暂未检测到新兴技能"
              description="当技能出现显著 Z-score 上升信号时会在此显示"
            />
          </div>
        </el-card>
      </div>

      <!-- LOOP-06: 新兴技能预警 -->
      <el-card
        v-if="evo.emergingAlerts.length > 0"
        v-loading="evo.alertsLoading"
        class="alerts-card"
      >
        <template #header>
          <div class="card-header">
            <span>新兴技能预警</span>
            <el-tag type="danger">
              {{ evo.emergingAlerts.length }}
            </el-tag>
          </div>
        </template>
        <!-- E5: 口径说明 — Z-score/可迁移性/预警信息的数据来源 -->
        <p class="alerts-note">
          依据技能时序 Z-score 检测（全量历史窗口），与上方「新兴技能」卡及 KPI「涌现技能数/预警数」同源。
        </p>
        <el-table
          :data="evo.emergingAlerts"
          size="small"
          stripe
        >
          <el-table-column
            prop="skill_name"
            label="技能"
          />
          <el-table-column
            label="级别"
            width="100"
          >
            <template #header>
              <span title="Z-score 分级：z>2.0 且频次≥3 且源≥3 → 涌现；z>1.5 → 上升；z<-1.5 → 下降">级别</span>
            </template>
            <template #default="{ row }">
              <el-tag
                :type="ALERT_LEVEL_TAG[row.level] ?? 'info'"
                size="small"
              >
                {{ ALERT_LEVEL_LABEL[row.level] ?? row.level }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="trend"
            label="趋势"
            width="80"
          >
            <template #default="{ row }">
              <span>{{ row.trend === 'rising' ? '↑' : row.trend === 'declining' ? '↓' : '→' }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="z_score"
            label="Z-score"
            width="80"
          >
            <template #header>
              <span title="当前频次相对历史均值的标准差倍数（|z| 越大信号越强）">Z-score</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="portability_score"
            label="可迁移性"
            width="90"
          >
            <template #header>
              <span title="技能跨领域岗位覆盖比例（EmergenceFinder.portability_score）">可迁移性</span>
            </template>
            <template #default="{ row }">
              <span>{{ row.portability_score != null ? Math.round(row.portability_score * 100) + '%' : '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="alert_message"
            label="预警信息"
            show-overflow-tooltip
          />
        </el-table>
      </el-card>

      <!-- 曲线图 -->
      <el-card
        v-loading="loading"
        class="chart-card"
      >
        <template #header>
          CII 分布（当前值）— 全部技能通胀指数分布
        </template>
        <VChart
          v-if="items.length"
          :option="chartOption"
          autoresize
          class="chart-h-lg"
        />
        <EmptyState
          v-else
          title="演化数据待生成"
          description="CII 时序分析运行后将自动填充"
        >
          <!-- 10-03 (D-12): 诚实空态 + 引导按钮（Celery 异步，已排队反馈，无 SSE） -->
          <el-button
            size="small"
            type="primary"
            :loading="analyzing"
            @click="triggerAnalyze"
          >
            触发演化分析
          </el-button>
          <a
            class="guide-doc-link"
            href="docs/design/星图StarMap-项目设计文档（含配图）v3.0.docx"
            target="_blank"
            rel="noopener"
          >
            查看文档
          </a>
        </EmptyState>
      </el-card>

      <!-- 技能对比 -->
      <el-card
        class="compare-card"
        shadow="hover"
      >
        <template #header>
          技能对比
        </template>
        <div class="compare-selectors">
          <el-select
            v-model="compareSkillA"
            placeholder="选择技能 A"
            clearable
            size="small"
            class="select-md"
          >
            <el-option
              v-for="item in items"
              :key="'A_' + item.skill_name"
              :label="item.skill_name"
              :value="item.skill_name"
            />
          </el-select>
          <span class="compare-vs">VS</span>
          <el-select
            v-model="compareSkillB"
            placeholder="选择技能 B"
            clearable
            size="small"
            class="select-md"
          >
            <el-option
              v-for="item in items"
              :key="'B_' + item.skill_name"
              :label="item.skill_name"
              :value="item.skill_name"
            />
          </el-select>
        </div>
        <VChart
          v-if="compareOption"
          :option="compareOption"
          autoresize
          class="chart-h-md mt-3"
        />
        <div
          v-else
          class="compare-placeholder"
        >
          选择两个技能进行对比分析
        </div>
      </el-card>

      <!-- 趋势概览表 -->
      <el-card class="table-card">
        <template #header>
          趋势概览
        </template>
        <el-table
          :data="items"
          size="small"
          stripe
          empty-text="暂无数据"
          @row-click="(row: TrendItem) => fetchChangelog(row.skill_name)"
        >
          <el-table-column
            prop="skill_name"
            label="技能"
            min-width="120"
          >
            <template #default="{ row }">
              <el-link type="primary">
                {{ row.skill_name }}
              </el-link>
            </template>
          </el-table-column>
          <el-table-column
            label="趋势"
            width="100"
          >
            <template #header>
              <span title="Z-score 检测分级：涌现/上升/平稳/下降">趋势</span>
            </template>
            <template #default="{ row }">
              <el-tag
                :type="trendTagType[row.trend]"
                size="small"
                effect="plain"
              >
                {{ trendLabel[row.trend] ?? row.trend }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="当前 CII"
            width="100"
          >
            <template #header>
              <span title="能力通胀指数：基准 100 = 频次前半段均值，>100 表示需求膨胀">当前 CII</span>
            </template>
            <template #default="{ row }">
              <b>{{ row.points?.[row.points.length - 1] ?? '-' }}</b>
            </template>
          </el-table-column>
          <el-table-column
            label="变化"
            width="100"
          >
            <template #header>
              <span title="CII 末点相对基准 100 的涨跌幅">变化</span>
            </template>
            <template #default="{ row }">
              <span
                v-if="row.points?.length"
                :class="row.points.at(-1)! >= 100 ? 'cii-up' : 'cii-down'"
              >
                {{ formatChange(row.points) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            label="置信度"
            width="90"
          >
            <template #header>
              <span title="由 Z-score 映射：clamp(0.5 + z/10, 0, 1)">置信度</span>
            </template>
            <template #default="{ row }">
              {{ ((row.confidence ?? 0) * 100).toFixed(0) }}%
            </template>
          </el-table-column>
          <el-table-column
            label="关联岗位"
            min-width="200"
          >
            <template #default="{ row }">
              <el-tag
                v-for="pos in row.related_positions"
                :key="pos"
                size="small"
                class="related-tag"
              >
                {{ pos }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 10-03 (D-11): 次区 — 演化路径/CII 历史/迁移性（复用已有数据源，无虚构估算） -->
      <el-card
        class="secondary-card"
        shadow="hover"
      >
        <template #header>
          <div class="card-header-row">
            <span>演化洞察</span><span class="card-header-badge">次区</span>
          </div>
        </template>
        <div class="secondary-grid">
          <!-- 演化路径：已有快照覆盖的岗位 -->
          <div class="secondary-block">
            <h4 class="secondary-title">
              演化路径
            </h4>
            <template v-if="trackedPositions.length">
              <el-tag
                v-for="pos in trackedPositions"
                :key="pos"
                size="small"
                effect="plain"
                class="related-tag"
              >
                {{ pos }}
              </el-tag>
            </template>
            <EmptyState
              v-else
              title="暂无演化路径"
              description="快照生成后将显示已覆盖岗位"
            />
          </div>
          <!-- CII 历史：全部技能当前 CII 概览（Top 10）— 快照级 CII 已在时间线卡内联展示 -->
          <div class="secondary-block">
            <h4 class="secondary-title">
              CII 历史
            </h4>
            <template v-if="ciiOverviewList.length">
              <el-table
                :data="ciiOverviewList.slice(0, 10)"
                size="small"
                stripe
                empty-text="暂无数据"
              >
                <el-table-column
                  prop="skill_name"
                  label="技能"
                  min-width="120"
                />
                <el-table-column
                  label="当前 CII"
                  width="90"
                >
                  <template #default="{ row }">
                    <span :class="row.last >= 100 ? 'cii-up' : 'cii-down'">{{ row.last }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </template>
            <EmptyState
              v-else
              title="暂无 CII 历史"
              description="CII 时序分析运行后将自动填充"
            />
          </div>
          <!-- 迁移性：复用 emerging alerts 的 portability_score -->
          <div class="secondary-block">
            <h4 class="secondary-title">
              迁移性
            </h4>
            <template v-if="portabilityAlerts.length">
              <div
                v-for="a in portabilityAlerts.slice(0, 8)"
                :key="a.skill_name"
                class="portability-row"
              >
                <span class="portability-name">{{ a.skill_name }}</span>
                <span class="portability-score">{{ Math.round((a.portability_score ?? 0) * 100) }}%</span>
              </div>
            </template>
            <EmptyState
              v-else
              title="暂无迁移性数据"
              description="涌现技能预警生成后将显示可迁移性得分"
            />
          </div>
        </div>
      </el-card>

      <!-- 演化详情抽屉 — extracted to EvolutionChangelogDrawer.vue -->
      <EvolutionChangelogDrawer
        v-model="drawerVisible"
        :skill-name="selectedSkillForDetail"
        :data="changelogData"
        :loading="changelogLoading"
        :evidence-open="evidenceDrawerOpen"
      />
    </div>
  </MainLayout>
</template>

<style scoped>
.evolution-page {
  min-height: 400px;
}

/* Phase 26: 业务说明横幅 — 已迁移到 BusinessBanner.vue */


.page-title {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}
.page-subtitle {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: 0;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.select-sm { width: 180px; }
.select-md { width: 240px; }
.ml-2 { margin-left: 8px; }
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── KPI Number Row (D-11) ── */
.kpi-number-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.kpi-number-card { text-align: center; padding: 4px 0; }
.kpi-number-label {
  font-size: 12px;
  color: var(--muted-foreground);
  margin-bottom: 6px;
}
.kpi-number-value {
  font-size: 26px;
  font-weight: 800;
  color: var(--foreground);
  line-height: 1.2;
}
/* E2: KPI 口径拆解行 */
.kpi-number-breakdown {
  font-size: 11px;
  color: var(--muted-foreground);
  margin-top: 4px;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* E2/E7: 全局数据口径说明 */
.explainer-card { margin-bottom: 16px; }

/* E3: 仪表盘口径注记 */
.gauge-note {
  font-size: 12px;
  color: var(--muted-foreground);
  margin: 8px 0 0;
  text-align: center;
}

/* E4: 新兴技能卡同源标记 */
.emerging-z { font-weight: 600; color: var(--muted-foreground); }

/* E5: 预警表口径说明行 */
.alerts-note {
  font-size: 12px;
  color: var(--muted-foreground);
  margin: 0 0 8px;
}

/* E1: 快照详情块 */
.secondary-hint {
  font-size: 11px;
  font-weight: 400;
  color: var(--muted-foreground);
  margin-left: 6px;
}
.snapshot-skill-chips { margin-bottom: 8px; }
.snapshot-meta {
  font-size: 11px;
  color: var(--muted-foreground);
  margin: 0;
}

/* ── Secondary zone (D-11) ── */
.secondary-card { margin-top: 16px; }
.secondary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}
.secondary-block { min-width: 0; }
.secondary-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--foreground);
  margin: 0 0 8px;
}
.portability-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  padding: 3px 0;
  color: var(--muted-foreground);
}
.portability-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.portability-score { font-weight: 600; color: var(--primary, #409eff); }

/* ── Empty state guide (D-12) ── */
.guide-doc-link {
  font-size: 13px;
  color: var(--primary, #409eff);
  text-decoration: none;
}
.guide-doc-link:hover { text-decoration: underline; }

/* ── Cards ── */
.card-header-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.card-header-badge {
  font-size: 11px;
  color: var(--success, #67c23a);
  background: rgba(103, 194, 83, 0.12);
  padding: 2px 6px;
  border-radius: 6px;
}
/* ── 仪表盘：加高加宽，避免紧凑感（Fix 1） ── */
.gauge-card { min-height: 340px; }
.emerging-card { min-height: 260px; }
.chart-h-gauge { height: 300px; }
.chart-h-lg { height: 380px; }
.chart-h-md { height: 280px; }

/* ── KPI Row ── */
.kpi-row {
  display: grid;
  grid-template-columns: 1.25fr 1.75fr;
  gap: 16px;
}

/* ── Timeline ── */
.timeline-card { margin-bottom: 16px; }
/* E1-2: 快照时间线内联详情（交互处即时可见） */
.snapshot-inline {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px dashed var(--border, #e4e7ed);
  border-radius: 8px;
  background: var(--card, #fff);
}
.snapshot-inline-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.snapshot-inline-title { font-size: 14px; font-weight: 600; color: var(--foreground); }
.snapshot-inline-date { font-size: 12px; color: var(--muted-foreground); }
.timeline-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.timeline-label { font-size: 13px; color: var(--muted-foreground); white-space: nowrap; }
.timeline-slider { flex: 1; }
.timeline-current { font-size: 13px; color: var(--muted-foreground); white-space: nowrap; }

/* ── Emerging skills ── */
.emerging-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
}
.emerging-item {
  cursor: pointer;
  padding: 8px 10px;
  border-radius: var(--radius-lg);
  background: var(--muted, rgba(148,163,184,0.08));
  transition: background 0.2s;
}
.emerging-item:hover { background: var(--muted, rgba(148,163,184,0.16)); }
.emerging-name { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
.emerging-meta { display: flex; align-items: center; justify-content: space-between; font-size: 12px; }
.emerging-cii { color: var(--muted-foreground); }
.pulse-tag { animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{ opacity:1; } 50%{ opacity:0.7; } }

/* ── Compare ── */
.compare-card { margin-top: 16px; }
.compare-selectors {
  display: flex;
  align-items: center;
  gap: 12px;
}
.compare-vs {
  font-weight: 700;
  color: var(--muted-foreground);
}
.compare-placeholder {
  text-align: center;
  padding: 40px;
  color: var(--muted-foreground);
}

/* ── Table ── */
.table-card { margin-top: 16px; }
.related-tag { margin: 2px 4px; }

/* ── CII indicators ── */
.cii-up { color: var(--success, #67c23a); }
.cii-down { color: var(--danger, #f56c6c); }

/* ── Empty state ── */
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 20px;
  color: var(--muted-foreground);
  text-align: center;
}
.empty-icon-wrapper { opacity: 0.4; }
</style>
