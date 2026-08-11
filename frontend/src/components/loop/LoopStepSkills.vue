<script setup lang="ts">
/**
 * LoopStepSkills — Step 2: Skill Extraction Results
 * Displays skill chips with is_new indicators, confidence, hallucination score.
 * Phase 07-02 D-05/D-06: also surfaces 技能数 / 信任度均值 / 实际 model_used
 * (云端秒级 vs 本地 fallback 解释).
 */
import { computed } from 'vue'
import type { StepResult } from '@/stores/loop'

const props = defineProps<{
  step: StepResult
  celebrated: boolean
  skills: { skill: string; is_new: boolean; confidence?: number }[]
}>()

// D-05: 口径拆解行 — 技能数 + 信任度均值
const skillCount = computed<number | null>(() => {
  const v = (props.step?.data as { skill_count?: number } | undefined)?.skill_count
  if (typeof v === 'number') return v
  return Array.isArray(props.skills) ? props.skills.length : null
})

const skillConfidenceAvg = computed<number | null>(() => {
  const v = (props.step?.data as { skill_confidence_avg?: number | null } | undefined)?.skill_confidence_avg
  return typeof v === 'number' ? v : null
})

const skillConfidencePct = computed(() =>
  skillConfidenceAvg.value == null ? '未评估' : `${(skillConfidenceAvg.value * 100).toFixed(0)}%`,
)

// D-06: model_used 透传 — 云端 vs 本地 fallback 标签
const modelUsed = computed<string | null>(() => {
  const v = (props.step?.data as { model_used?: string | null } | undefined)?.model_used
  return typeof v === 'string' && v.length > 0 ? v : null
})

const isLocalFallback = computed(() => {
  if (!modelUsed.value) return false
  // Convention from M6: local fallback models include '-fallback' suffix
  return modelUsed.value.toLowerCase().includes('fallback')
})

// Backwards-compat metric values (legacy fields still used by some stores)
const legacyConfidence = computed<number | null>(() => {
  const v = (props.step?.data as { confidence?: number | null } | undefined)?.confidence
  return typeof v === 'number' ? v : null
})

const legacyHallucination = computed<number | null>(() => {
  const v = (props.step?.data as { hallucination_score?: number | null } | undefined)?.hallucination_score
  return typeof v === 'number' ? v : null
})

const legacyHallucinationType = computed<'info' | 'warning' | 'success'>(() => {
  const v = legacyHallucination.value
  if (v == null) return 'info'
  return v > 0.3 ? 'warning' : 'success'
})

const legacyHallucinationLabel = computed(() => {
  const v = legacyHallucination.value
  return v == null ? '未评估' : `${(v * 100).toFixed(0)}%`
})
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
            <span class="step-num">2</span>
            技能提取结果
          </h2>
          <div
            v-if="step?.data"
            class="sc-metrics"
          >
            <el-tag
              type="info"
              size="small"
              effect="plain"
            >
              技能数: {{ skillCount ?? '—' }}
            </el-tag>
            <el-tag
              type="info"
              size="small"
              effect="plain"
            >
              信任度均值: {{ skillConfidencePct }}
            </el-tag>
            <el-tag
              v-if="modelUsed"
              :type="isLocalFallback ? 'warning' : 'success'"
              size="small"
              effect="plain"
            >
              模型: {{ modelUsed }}{{ isLocalFallback ? ' (本地，预计较慢)' : '' }}
            </el-tag>
            <el-tag
              v-if="legacyConfidence != null"
              type="info"
              size="small"
              effect="plain"
            >
              置信度: {{ ((legacyConfidence as number) * 100).toFixed(0) }}%
            </el-tag>
            <el-tag
              :type="legacyHallucinationType"
              size="small"
              effect="plain"
            >
              幻觉评分: {{ legacyHallucinationLabel }}
            </el-tag>
          </div>
        </div>
      </template>

      <div
        v-if="step?.data"
        class="extracted-skills stagger"
      >
        <div
          v-for="(skill, idx) in skills"
          :key="skill.skill"
          class="skill-chip anim-fade-in-up"
          :class="{ 'skill-new': skill.is_new, 'skill-existing': !skill.is_new }"
          :style="{ animationDelay: (idx * 60) + 'ms' }"
        >
          <span class="chip-marker">{{ skill.is_new ? '🆕' : '✅' }}</span>
          <span class="chip-name">{{ skill.skill }}</span>
          <span
            v-if="skill.confidence"
            class="chip-conf"
          >{{ (skill.confidence * 100).toFixed(0) }}%</span>
        </div>
        <div
          v-if="skills.length === 0"
          class="empty-skills"
        >
          暂无提取结果
        </div>
      </div>

      <div
        v-if="step?.status === 'running'"
        v-loading="true"
        style="min-height: 100px"
      />
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
.sc-metrics {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

/* ── Step 2: Extracted Skills ── */
.extracted-skills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-2) 0;
}
.skill-chip {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--font-size-sm);
  font-weight: 500;
  transition: all 0.3s var(--ease-out);
}
.skill-new {
  background: color-mix(in srgb, var(--success, #22c55e) 12%, var(--card));
  border: 1px solid color-mix(in srgb, var(--success, #22c55e) 30%, var(--border));
  color: var(--success, #16a34a);
}
.skill-existing {
  background: color-mix(in srgb, var(--primary) 8%, var(--card));
  border: 1px solid color-mix(in srgb, var(--primary) 20%, var(--border));
  color: var(--primary);
}
.chip-marker {
  font-size: 12px;
}
.chip-conf {
  font-size: 11px;
  opacity: 0.7;
  font-variant-numeric: tabular-nums;
}
.empty-skills {
  text-align: center;
  padding: var(--space-6);
  color: var(--muted-foreground);
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
