<script setup lang="ts">
/**
 * 差距分析报告 — Step 3 子组件
 * 展示匹配分数、已匹配技能、技能差距明细和诊断历史
 */
import { computed } from 'vue'
import { Guide, Download } from '@element-plus/icons-vue'
import { useMatchStore } from '@/stores/match'

const props = defineProps<{
  targetPosition: string
}>()

const emit = defineEmits<{
  goLearning: []
  goBack: []
  exportReport: []
}>()

const matchStore = useMatchStore()

const matchResult = computed(() => matchStore.result)
const gapSkills = computed(() => matchResult.value?.skill_gap_detail ?? [])
const matchedSkills = computed(() => matchResult.value?.matched_skills ?? [])
const matchScore = computed(() => matchResult.value?.match_score ?? 0)

// FLOW-02-S3: 分数差值卡片 —— 对比当前匹配分数与历史最近一次同岗位匹配分数
const previousScore = computed(() => {
  const currentPosition = props.targetPosition
  const currentId = matchResult.value?.match_id
  // Find the most recent history entry for the same position, excluding current
  const prev = matchStore.historyList.find(
    (h) => h.target_position === currentPosition && h.match_id !== currentId,
  )
  return prev ? prev.match_score ?? null : null
})
const scoreDelta = computed(() => {
  if (previousScore.value === null || !matchScore.value) return null
  return Math.round((matchScore.value - previousScore.value) * 100)
})

// 学习路径数据（供导出用）
const learningPaths = computed(() => {
  return gapSkills.value.map(g => {
    const pathArr = Array.isArray(g.learning_path) ? g.learning_path : []
    return {
      skill: g.skill,
      importance: g.importance,
      gapLevel: g.gap_level,
      path: pathArr.length > 0 ? pathArr.join(' → ') : '—',
      pathArray: pathArr,
    }
  })
})

function handleExport() {
  const report = {
    match_id: matchResult.value?.match_id,
    target_position: props.targetPosition,
    match_score: matchScore.value,
    matched_skills: matchedSkills.value,
    missing_required: matchResult.value?.missing_required ?? [],
    missing_bonus: matchResult.value?.missing_bonus ?? [],
    gap_skills: gapSkills.value,
    skill_gap_detail: matchResult.value?.skill_gap_detail ?? [],
    recommendations: matchResult.value?.recommendations ?? [],
    learning_paths: learningPaths.value,
    overall_assessment: matchResult.value?.overall_assessment ?? '',
    estimated_learning_time: matchResult.value?.estimated_learning_time ?? '',
    exported_at: new Date().toISOString(),
  }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `match-report-${props.targetPosition}.json`; a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="step-content">
    <div class="step-card">
      <div class="sc-header">
        <div class="sc-header-row">
          <div>
            <h2 class="sc-title">
              差距分析报告
            </h2>
            <p class="sc-desc">
              综合评估你的岗位匹配度
            </p>
          </div>
          <el-button
            text
            @click="emit('goBack')"
          >
            ← 返回
          </el-button>
        </div>
      </div>

      <div v-if="matchStore.result">
        <!-- Summary -->
        <div class="report-summary anim-scale-in">
          <div class="rs-score">
            <span class="rs-value">{{ Math.round((matchStore.result.match_score ?? 0) * 100) }}</span>
            <span class="rs-unit">%</span>
          </div>
          <!-- FLOW-02-S3: 分数差值卡片 -->
          <div
            v-if="scoreDelta !== null"
            class="rs-delta"
            :class="{ 'rs-delta--up': scoreDelta > 0, 'rs-delta--down': scoreDelta < 0 }"
          >
            <span class="rs-delta-icon">{{ scoreDelta > 0 ? '↑' : scoreDelta < 0 ? '↓' : '→' }}</span>
            <span class="rs-delta-text">
              匹配分数从 {{ Math.round((previousScore ?? 0) * 100) }}% 提升至 {{ Math.round(matchScore * 100) }}%
            </span>
            <span class="rs-delta-value">({{ scoreDelta > 0 ? '+' : '' }}{{ scoreDelta }}%)</span>
          </div>
          <div class="rs-detail">
            <div class="rs-row">
              <span class="rs-label">匹配技能</span>
              <div class="rs-tags stagger">
                <el-tag
                  v-for="s in matchedSkills"
                  :key="s"
                  type="success"
                  size="small"
                  class="anim-fade-in-up"
                >
                  {{ s }}
                </el-tag>
                <span
                  v-if="!matchedSkills.length"
                  class="rs-empty"
                >无</span>
              </div>
            </div>
            <div class="rs-row">
              <span class="rs-label">综合评估</span>
              <span class="rs-text">{{ matchResult?.overall_assessment ?? '等待评估结果生成' }}</span>
            </div>
            <div
              v-if="matchResult?.estimated_learning_time"
              class="rs-row"
            >
              <span class="rs-label">预计学习时间</span>
              <span class="rs-text">{{ matchResult?.estimated_learning_time }}</span>
            </div>
          </div>
        </div>

        <!-- Gap table -->
        <h3 class="table-title">
          技能差距明细
        </h3>
        <el-table
          :data="gapSkills"
          stripe
          class="full-width-table"
        >
          <el-table-column
            prop="skill"
            label="技能"
            min-width="140"
          />
          <el-table-column
            label="重要性"
            width="100"
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
            label="差距程度"
            width="120"
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
          <el-table-column label="推荐学习路径">
            <template #default="{ row }">
              <div
                v-if="Array.isArray(row.learning_path) && row.learning_path.length > 0"
                class="lp-cell"
              >
                <div
                  v-for="(step, si) in row.learning_path"
                  :key="si"
                  class="lp-cell-step"
                >
                  <span
                    class="lp-cell-dot"
                    :class="{ 'lp-cell-dot--final': si === row.learning_path.length - 1 }"
                  />
                  <span class="lp-cell-text">{{ step }}</span>
                  <span
                    v-if="si < row.learning_path.length - 1"
                    class="lp-cell-arrow"
                  >→</span>
                </div>
              </div>
              <span
                v-else
                class="lp-cell-empty"
              >—</span>
            </template>
          </el-table-column>
        </el-table>

        <div class="step-actions">
          <el-button
            type="primary"
            size="large"
            :icon="Guide"
            @click="emit('goLearning')"
          >
            查看学习路径
          </el-button>
          <el-button
            size="large"
            :icon="Download"
            @click="handleExport"
          >
            导出报告
          </el-button>
        </div>
      </div>

      <div
        v-else
        class="step-empty"
      >
        诊断尚未开始，请完成前序步骤
      </div>
    </div>
  </div>

  <!-- 历史记录面板 -->
  <div
    v-if="matchStore.historyList.length > 0"
    class="step-content"
  >
    <div class="step-card">
      <div class="sc-header">
        <h2 class="sc-title">
          诊断历史
        </h2>
        <p class="sc-desc">
          最近的匹配诊断记录
        </p>
      </div>
      <el-table
        :data="matchStore.historyList"
        stripe
        size="small"
        class="full-width-table"
      >
        <el-table-column
          prop="target_position"
          label="目标岗位"
          min-width="140"
        />
        <el-table-column
          label="匹配分数"
          width="100"
        >
          <template #default="{ row }">
            <span :class="row.match_score >= 0.75 ? 'score-high' : row.match_score >= 0.5 ? 'score-mid' : 'score-low'">
              {{ Math.round(row.match_score * 100) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column
          label="匹配技能"
          min-width="200"
        >
          <template #default="{ row }">
            <el-tag
              v-for="s in row.matched_skills?.slice(0, 5)"
              :key="s"
              size="small"
              type="success"
              class="mr-1"
            >
              {{ s }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="时间"
          width="160"
        >
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleString() : '—' }}
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.step-content {
  animation: fade-in-up 0.35s var(--ease-out);
}
@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.step-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-2xl);
  padding: var(--space-8);
  box-shadow: var(--shadow-xs);
  position: relative;
  overflow: hidden;
}
.step-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary), var(--chart-2));
  opacity: 0.8;
}
.sc-header { margin-bottom: var(--space-6); }
.sc-header-row { display: flex; justify-content: space-between; align-items: flex-start; }
.sc-title {
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}
.sc-desc {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}
.step-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
  margin-top: var(--space-6);
}
.step-empty {
  text-align: center;
  color: var(--muted-foreground);
  padding: var(--space-10) 0;
  font-size: var(--font-size-sm);
}

/* Report Summary */
.report-summary {
  display: flex;
  gap: var(--space-6);
  padding: var(--space-6);
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 4%, var(--card)), var(--card));
  border: 1px solid color-mix(in srgb, var(--primary) 12%, var(--border));
  border-radius: var(--radius-2xl);
  margin-bottom: var(--space-6);
  position: relative;
}
.report-summary::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--primary), var(--chart-2));
  border-radius: 2px 2px 0 0;
}
.rs-score { display: flex; align-items: baseline; flex-shrink: 0; }
.rs-value {
  font-size: 3rem;
  font-weight: 900;
  background: linear-gradient(135deg, var(--primary), var(--chart-1));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
}
.rs-unit {
  font-size: var(--font-size-xl);
  color: var(--muted-foreground);
  margin-left: var(--space-1);
  font-weight: 600;
}
/* FLOW-02-S3: 分数差值卡片 */
.rs-delta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-sm);
  font-weight: 600;
  margin-top: var(--space-2);
  animation: fade-in-up 0.4s var(--ease-out);
}
.rs-delta--up {
  background: color-mix(in srgb, var(--success) 10%, var(--card));
  color: var(--success);
  border: 1px solid color-mix(in srgb, var(--success) 20%, var(--border));
}
.rs-delta--down {
  background: color-mix(in srgb, var(--danger) 10%, var(--card));
  color: var(--danger);
  border: 1px solid color-mix(in srgb, var(--danger) 20%, var(--border));
}
.rs-delta-icon { font-size: var(--font-size-lg); font-weight: 900; }
.rs-delta-text { color: var(--foreground); font-weight: 500; }
.rs-delta-value { font-variant-numeric: tabular-nums; }
.rs-detail { flex: 1; display: flex; flex-direction: column; gap: var(--space-2-5); }
.rs-row { display: flex; align-items: flex-start; gap: var(--space-3); font-size: var(--font-size-sm); }
.rs-label { color: var(--muted-foreground); min-width: 80px; flex-shrink: 0; font-weight: 500; }
.rs-text { color: var(--foreground); line-height: var(--leading-relaxed); }
.rs-tags { display: flex; flex-wrap: wrap; gap: var(--space-1); }
.rs-empty { color: var(--muted-foreground); }
.table-title {
  font-size: var(--font-size-base);
  font-weight: 700;
  color: var(--foreground);
  margin: var(--space-6) 0 var(--space-3);
  letter-spacing: var(--tracking-tight);
}
.full-width-table { width: 100%; }
.mr-1 { margin-right: var(--space-1); }
.score-high { color: var(--success); font-weight: 700; }
.score-mid { color: var(--warning); font-weight: 700; }
.score-low { color: var(--danger); font-weight: 700; }

/* Learning Path Cell (in gap table) */
.lp-cell { display: flex; align-items: center; flex-wrap: wrap; gap: 2px; }
.lp-cell-step { display: inline-flex; align-items: center; gap: 2px; }
.lp-cell-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--muted-foreground); flex-shrink: 0;
}
.lp-cell-dot--final { background: var(--success); }
.lp-cell-text { font-size: var(--font-size-xs); color: var(--foreground); white-space: nowrap; }
.lp-cell-arrow { color: var(--muted-foreground); font-size: 10px; margin: 0 2px; }
.lp-cell-empty { color: var(--muted-foreground); font-size: var(--font-size-sm); }
</style>
