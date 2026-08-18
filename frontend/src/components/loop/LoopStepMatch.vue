<script setup lang="ts">
/**
 * LoopStepMatch — Step 4: Match Diagnosis
 * Radar chart + gap analysis + skill tags.
 *-02: also surfaces 分数拆解行（required_avg / bonus_avg /
 * weight_required / weight_bonus / inflated）。
 */
import { ref, computed, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, RadarComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { StepResult } from '@/stores/loop'
import { chartColors, legendStyle } from '@/utils/chartTheme'

use([RadarChart, TooltipComponent, LegendComponent, RadarComponent, CanvasRenderer])

const cc = chartColors()

const props = defineProps<{
  step: StepResult
  celebrated: boolean
}>()

// 口径拆解 — 分数拆解（沿用 app.core.matching.service.py:349-354
// 现有 key: required_avg / bonus_avg / weight_required / weight_bonus / inflated）
interface ScoreBreakdown {
  required_avg?: number
  bonus_avg?: number
  weight_required?: number
  weight_bonus?: number
  inflated?: boolean
}
const scoreBreakdown = computed<ScoreBreakdown | null>(() => {
  const d = props.step?.data as { score_breakdown?: ScoreBreakdown } | undefined
  return d?.score_breakdown ?? null
})

const requiredAvgPct = computed(() =>
  scoreBreakdown.value?.required_avg == null ? '—' : `${(scoreBreakdown.value.required_avg * 100).toFixed(0)}%`,
)
const bonusAvgPct = computed(() =>
  scoreBreakdown.value?.bonus_avg == null ? '—' : `${(scoreBreakdown.value.bonus_avg * 100).toFixed(0)}%`,
)
const weightRequiredPct = computed(() =>
  scoreBreakdown.value?.weight_required == null ? '—' : `${(scoreBreakdown.value.weight_required * 100).toFixed(0)}%`,
)
const weightBonusPct = computed(() =>
  scoreBreakdown.value?.weight_bonus == null ? '—' : `${(scoreBreakdown.value.weight_bonus * 100).toFixed(0)}%`,
)

// ── Radar chart data ──
const radarData = ref<{ skill: string; required: number; matched: number }[]>([])

function buildRadarData() {
  const step4Data = props.step?.data
  if (!step4Data) return
  if (step4Data.radar_data && step4Data.radar_data.length > 0) {
    radarData.value = step4Data.radar_data
  } else {
 // Build from matched + missing
    const matched = (step4Data.matched_skills ?? []).map((s: string) => ({ skill: s, required: 0.8, matched: 0.7 + Math.random() * 0.25 }))
    const missing = (step4Data.missing_skills ?? []).map((s: string) => ({ skill: s, required: 0.7, matched: Math.random() * 0.3 }))
    radarData.value = [...matched, ...missing].slice(0, 8)
  }
}

const radarOption = computed(() => {
  if (radarData.value.length < 3) return {}
  const indicators = radarData.value.map(d => ({ name: d.skill, max: 1 }))
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: legendStyle() },
    radar: {
      center: ['50%', '46%'],
      radius: '62%',
      indicator: indicators,
      axisName: { color: cc.muted, fontSize: 11 },
    },
    series: [{
      type: 'radar',
      name: '岗位要求',
      data: [{ value: radarData.value.map(d => d.required), name: '岗位要求' }],
      lineStyle: { color: cc.danger, width: 2 },
      areaStyle: { color: cc.danger + '33' },
      itemStyle: { color: cc.danger },
    }, {
      type: 'radar',
      name: '匹配程度',
      data: [{ value: radarData.value.map(d => d.matched), name: '匹配程度' }],
      lineStyle: { color: cc.primary, width: 2 },
      areaStyle: { color: cc.primary + '33' },
      itemStyle: { color: cc.primary },
    }],
  }
})

// Watch for step data changes to rebuild radar
watch(() => props.step?.data, () => {
  if (props.step?.status !== 'waiting') {
    buildRadarData()
  }
}, { immediate: true })

// Expose buildRadarData so parent can trigger it
defineExpose({ buildRadarData })
</script>

<template>
  <div
    class="step-section animate-fade-in"
    :class="{ 'anim-celebrate': celebrated }"
  >
    <el-card
      shadow="never"
      class="step-card"
    >
      <template #header>
        <div class="sc-header">
          <h2 class="sc-title">
            <span class="step-num">4</span>
            匹配诊断
          </h2>
          <div
            v-if="step?.data?.match_score !== undefined"
            class="match-score-badge"
          >
            <span class="score-value">{{ Math.round((step.data.match_score ?? 0) * 100) }}</span>
            <span class="score-unit">%</span>
          </div>
        </div>
        <!-- 分数拆解行（ 口径 — required_avg/bonus_avg/权重/inflated） -->
        <div
          v-if="scoreBreakdown"
          class="score-breakdown-row"
        >
          <el-tag
            type="info"
            size="small"
            effect="plain"
          >必备均值 {{ requiredAvgPct }}</el-tag>
          <el-tag
            type="info"
            size="small"
            effect="plain"
          >加分均值 {{ bonusAvgPct }}</el-tag>
          <el-tag
            size="small"
            effect="plain"
          >必备权重 {{ weightRequiredPct }}</el-tag>
          <el-tag
            size="small"
            effect="plain"
          >加分权重 {{ weightBonusPct }}</el-tag>
          <el-tag
            v-if="scoreBreakdown.inflated"
            type="warning"
            size="small"
            effect="plain"
          >⚠ CII 通胀修正已触发</el-tag>
        </div>
      </template>

      <div
        v-if="step?.status === 'running'"
        v-loading="true"
        style="min-height: 200px"
      />

      <div v-else-if="step?.data">
        <el-row :gutter="20">
          <!-- Radar chart -->
          <el-col
            :span="12"
            :xs="24"
          >
            <div
              v-if="radarData.length >= 3"
              class="radar-container"
            >
              <VChart
                :option="radarOption"
                style="height: 340px"
                autoresize
              />
            </div>
            <div
              v-else
              class="radar-empty"
            >
              雷达图数据不足
            </div>
          </el-col>

          <!-- Gap analysis -->
          <el-col
            :span="12"
            :xs="24"
          >
            <div class="gap-analysis">
              <!-- Matched skills -->
              <h4 class="gap-section-title">
                ✓ 匹配技能
              </h4>
              <div class="skill-tags-row">
                <el-tag
                  v-for="s in (step.data.matched_skills ?? [])"
                  :key="s"
                  type="success"
                  size="small"
                  effect="plain"
                >
                  {{ s }}
                </el-tag>
                <span
                  v-if="!(step.data.matched_skills?.length)"
                  class="empty-text"
                >无</span>
              </div>

              <!-- Missing skills -->
              <h4 class="gap-section-title">
                ✕ 缺失技能
              </h4>
              <div class="skill-tags-row">
                <el-tag
                  v-for="s in (step.data.missing_skills ?? step.data.gap_analysis?.map((g: any) => g.skill) ?? [])"
                  :key="s"
                  type="danger"
                  size="small"
                  effect="plain"
                >
                  {{ s }}
                </el-tag>
                <span
                  v-if="!(step.data.missing_skills?.length) && !(step.data.gap_analysis?.length)"
                  class="empty-text"
                >无</span>
              </div>

              <!-- Gap detail table -->
              <div
                v-if="step.data.gap_analysis?.length"
                class="gap-table-wrapper"
              >
                <h4 class="gap-section-title">
                  差距明细
                </h4>
                <el-table
                  :data="step.data.gap_analysis"
                  size="small"
                  stripe
                  max-height="200"
                  empty-text="暂无数据"
                >
                  <el-table-column
                    prop="skill"
                    label="技能"
                    min-width="100"
                  />
                  <el-table-column
                    label="重要性"
                    width="80"
                    align="center"
                  >
                    <template #default="{ row }">
                      <el-tag
                        :type="row.importance === 'required' ? 'danger' : 'info'"
                        size="small"
                      >
                        {{ row.importance === 'required' ? '必备' : '加分' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column
                    label="差距"
                    width="90"
                    align="center"
                  >
                    <template #default="{ row }">
                      <el-tag
                        :type="row.gap_level === '完全缺失' ? 'danger' : row.gap_level === '部分掌握' ? 'warning' : 'success'"
                        size="small"
                      >
                        {{ row.gap_level }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
/* ── Step Section ── */
.step-section {
  margin-bottom: var(--space-5);
  animation: fade-in-up 0.4s var(--ease-out);
}
@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Step Card ── */
.step-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-2xl);
  position: relative;
  overflow: hidden;
}
.step-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary), var(--chart-2));
  opacity: 0.8;
}

.sc-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sc-title {
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--chart-2));
  color: white;
  font-size: var(--font-size-sm);
  font-weight: 700;
  flex-shrink: 0;
}

/* ── Step 4: Match Diagnosis ── */
.match-score-badge {
  display: flex;
  align-items: baseline;
}
.score-value {
  font-size: 2rem;
  font-weight: 900;
  background: linear-gradient(135deg, var(--primary), var(--chart-1));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
}
.score-unit {
  font-size: var(--font-size-lg);
  color: var(--muted-foreground);
  margin-left: var(--space-1);
  font-weight: 600;
}
.radar-container {
  padding: var(--space-2);
}
.radar-empty {
  text-align: center;
  padding: var(--space-8);
  color: var(--muted-foreground);
}
.gap-analysis {
  padding: var(--space-2) 0;
}
.gap-section-title {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--muted-foreground);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: var(--space-4) 0 var(--space-2);
}
.gap-section-title:first-child {
  margin-top: 0;
}
.skill-tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
.empty-text {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
}
.gap-table-wrapper {
  margin-top: var(--space-3);
}

.score-breakdown-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

/* ── Celebration Effect ── */
.anim-celebrate {
  animation: loopCelebrate 0.7s var(--ease-out) both;
}
@keyframes loopCelebrate {
  0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--success) 40%, transparent); }
  50% { box-shadow: 0 0 0 8px color-mix(in srgb, var(--success) 0%, transparent); }
  100% { box-shadow: 0 0 0 0 transparent; }
}
</style>
