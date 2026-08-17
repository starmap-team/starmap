<script setup lang="ts">
/**
 * LoopStepLearning — Step 5: Learning Path
 * Path flow items + prerequisite graph.
 */
import { computed } from 'vue'
import type { StepResult } from '@/stores/loop'

const props = defineProps<{
  step: StepResult
  celebrated: boolean
}>()

const learningPaths = computed(() => {
  const step5Data = props.step?.data
  if (!step5Data) return []
  return step5Data.paths ?? step5Data.learning_paths ?? []
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
            <span class="step-num">5</span>
            学习路径
          </h2>
          <div
            v-if="step?.data?.estimated_total_hours"
            class="est-time-badge"
          >
            预计 {{ step.data.estimated_total_hours }}h
          </div>
        </div>
      </template>

      <div
        v-if="step?.status === 'running'"
        v-loading="true"
        style="min-height: 100px"
      />

      <div v-else-if="learningPaths.length > 0">
        <!-- Learning path flow -->
        <div class="path-flow stagger">
          <div
            v-for="(item, idx) in learningPaths"
            :key="idx"
            class="path-item anim-fade-in-up"
            :style="{ animationDelay: (idx * 80) + 'ms' }"
          >
            <div class="path-num">
              {{ idx + 1 }}
            </div>
            <div class="path-info">
              <div class="path-skill-name">
                {{ item.skill ?? item.name ?? item }}
              </div>
              <div
                v-if="item.estimated_hours || item.hours"
                class="path-hours"
              >
                ≈ {{ item.estimated_hours ?? item.hours }}h
              </div>
              <div
                v-if="item.prerequisites?.length"
                class="path-prereq"
              >
                前置: {{ item.prerequisites.join(', ') }}
              </div>
            </div>
            <div
              v-if="idx < learningPaths.length - 1"
              class="path-arrow"
            >
              →
            </div>
          </div>
        </div>

        <!-- Prerequisite graph (simple visual) -->
        <div
          v-if="learningPaths.some((p: Record<string, unknown>) => p.prerequisites?.length)"
          class="prereq-section"
        >
          <h4 class="gap-section-title">
            前置条件关系
          </h4>
          <div class="prereq-list">
            <div
              v-for="(item, idx) in learningPaths.filter((p: Record<string, unknown>) => p.prerequisites?.length)"
              :key="idx"
              class="prereq-item"
            >
              <span class="prereq-arrow">{{ item.prerequisites.join(' + ') }}</span>
              <span class="prereq-arrow-icon">→</span>
              <span class="prereq-target">{{ item.skill ?? item.name }}</span>
            </div>
          </div>
        </div>
      </div>

      <div
        v-else
        class="empty-paths"
      >
        暂无学习路径数据
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

/* ── Step 5: Learning Path ── */
.path-flow {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3) 0;
}
.path-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--muted);
  border-radius: var(--radius-lg);
  padding: var(--space-2) var(--space-4);
  transition: transform 0.2s var(--ease-out);
}
.path-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}
.path-num {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--chart-2));
  color: white;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.path-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.path-skill-name {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--foreground);
}
.path-hours {
  font-size: 11px;
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
}
.path-prereq {
  font-size: 11px;
  color: var(--warning);
}
.path-arrow {
  font-size: var(--font-size-lg);
  color: var(--muted-foreground);
  font-weight: 300;
}
.est-time-badge {
  font-size: var(--font-size-sm);
  color: var(--primary);
  font-weight: 600;
  background: color-mix(in srgb, var(--primary) 8%, var(--card));
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
}
.prereq-section {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border);
}
.gap-section-title {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--muted-foreground);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: var(--space-4) 0 var(--space-2);
}
.prereq-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.prereq-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}
.prereq-arrow {
  color: var(--muted-foreground);
}
.prereq-arrow-icon {
  color: var(--primary);
  font-weight: 600;
}
.prereq-target {
  color: var(--foreground);
  font-weight: 600;
}
.empty-paths {
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
