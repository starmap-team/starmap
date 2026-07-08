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
import MainLayout from '@/layouts/MainLayout.vue'
import { useEvolutionStore } from '@/stores/evolution'
import type { TrendItem } from '@/stores/evolution'
import { useEvolutionCharts } from '@/composables/useEvolutionCharts'
import { useEvolutionActions } from '@/composables/useEvolutionActions'
import { formatChange, TREND_LABEL, TREND_TAG_TYPE } from '@/composables/useEvolutionFormatters'
// ponytail: alias uppercase constants to camelCase for template binding without renaming template
const trendLabel = TREND_LABEL
const trendTagType = TREND_TAG_TYPE
import EvolutionChangelogDrawer from '@/components/EvolutionChangelogDrawer.vue'

use([CanvasRenderer, LineChart, BarChart, GaugeChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const evo = useEvolutionStore()

// Aliases for template binding (store-backed)
const items = computed(() => evo.trendItems)
const quarters = computed(() => evo.quarters)
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
const { chartOption, emergingSkills, ciiGaugeOption, compareOption } = useEvolutionCharts(
  items, quarters, selectedSkill, compareSkillA, compareSkillB,
)

// Drawer / fetch handlers / snapshot state (extracted — Phase 7 D round 8)
const {
  drawerVisible,
  selectedSkillForDetail,
  snapshotIndex,
  selectedSnapshotDate,
  fetchTrends,
  fetchSnapshots,
  fetchChangelog,
  onSnapshotChange,
} = useEvolutionActions(evo)

onMounted(() => {
  void fetchTrends()
  void fetchSnapshots()
})
</script>

<template>
  <MainLayout>
    <div class="evolution-page animate-fade-in">
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
              {{ selectedSnapshotDate }}
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
            :format-tooltip="(idx: number) => snapshots[idx]?.snapshot_date ?? ''"
            class="timeline-slider"
            @change="onSnapshotChange"
          />
          <span class="timeline-current">{{ selectedSnapshotDate || '—' }}</span>
        </div>
      </el-card>
      <el-card
        v-else-if="!snapshotsLoading"
        class="timeline-card"
        shadow="never"
      >
        <div class="custom-empty">
          <p class="empty-text">
            暂无快照数据
          </p>
          <p class="empty-hint-text">
            演化快照生成后将显示时间线滑块
          </p>
        </div>
      </el-card>

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
          <div
            v-else
            class="custom-empty"
          >
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
              ><path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-3 3" /></svg>
            </div><p class="empty-text">
              图表数据为空
            </p><p class="empty-hint-text">
              技能 CII 数据将在分析完成后展示
            </p>
          </div>
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
                rising
              </el-tag>
            </div>
          </template>
          <div class="emerging-grid">
            <div
              v-for="skill in emergingSkills"
              :key="skill.skill_name"
              class="emerging-item"
              @click="fetchChangelog(skill.skill_name)"
            >
              <div class="emerging-name">
                {{ skill.skill_name }}
              </div>
              <div class="emerging-meta">
                <span class="emerging-cii">CII {{ skill.points?.[skill.points.length - 1] ?? '-' }}</span>
                <el-tag
                  size="small"
                  type="success"
                  effect="plain"
                  class="pulse-tag"
                >
                  ↑ {{ ((skill.confidence ?? 0) * 100).toFixed(0) }}%
                </el-tag>
              </div>
            </div>
            <div
              v-if="!emergingSkills.length"
              class="custom-empty"
            >
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
                ><path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-3 3" /></svg>
              </div><p class="empty-text">
                暂未检测到新兴技能
              </p><p class="empty-hint-text">
                当技能 CII 指数出现显著上升时会在此显示
              </p>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 曲线图 -->
      <el-card
        v-loading="loading"
        class="chart-card"
      >
        <template #header>
          CII 时序趋势
        </template>
        <VChart
          v-if="items.length"
          :option="chartOption"
          autoresize
          class="chart-h-lg"
        />
        <div
          v-else
          class="custom-empty"
        >
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
            ><ellipse
              cx="12"
              cy="5"
              rx="9"
              ry="3"
            /><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" /><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" /></svg>
          </div><p class="empty-text">
            演化数据待生成
          </p><p class="empty-hint-text">
            CII 时序分析运行后将自动填充
          </p>
        </div>
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
            <template #default="{ row }">
              <b>{{ row.points?.[row.points.length - 1] ?? '-' }}</b>
            </template>
          </el-table-column>
          <el-table-column
            label="变化"
            width="100"
          >
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

      <!-- 演化详情抽屉 — extracted to EvolutionChangelogDrawer.vue -->
      <EvolutionChangelogDrawer
        v-model="drawerVisible"
        :skill-name="selectedSkillForDetail"
        :data="changelogData"
        :loading="changelogLoading"
      />
    </div>
  </MainLayout>
</template>

<style scoped>
.evolution-page {
  min-height: 400px;
}
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
.gauge-card, .emerging-card { min-height: 260px; }
.chart-h-gauge { height: 240px; }
.chart-h-lg { height: 380px; }
.chart-h-md { height: 280px; }

/* ── KPI Row ── */
.kpi-row {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 16px;
}

/* ── Timeline ── */
.timeline-card { margin-bottom: 16px; }
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
  border-radius: 8px;
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
.empty-text { font-size: 14px; margin: 0; }
.empty-hint-text { font-size: 12px; opacity: 0.7; margin: 0; }
</style>
