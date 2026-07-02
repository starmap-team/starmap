<script setup lang="ts">
/**
 * 闭环时间线组件
 * 5步流程：JD输入 → 技能提取 → 图谱更新 → 匹配诊断 → 学习路径
 * 状态：waiting=灰, running=蓝动画, success=绿, degraded=黄, failed=红
 */
import { computed } from 'vue'
import type { StepResult } from '@/stores/loop'

const props = defineProps<{
  steps: StepResult[]
  activeStep: number
}>()

const emit = defineEmits<{
  (e: 'step-click', step: number): void
}>()

const stepIcons: Record<number, string> = {
  1: '📝',
  2: '🔍',
  3: '🔗',
  4: '📊',
  5: '🗺️',
}

function statusClass(status: string): string {
  return `status-${status}`
}

function formatDuration(ms?: number): string {
  if (!ms) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
</script>

<template>
  <div class="loop-timeline">
    <div
      v-for="(step, idx) in steps"
      :key="step.step"
      class="tl-step"
      :class="[
        statusClass(step.status),
        { 'tl-active': idx === activeStep, 'tl-clickable': step.status !== 'waiting' }
      ]"
      @click="step.status !== 'waiting' && emit('step-click', idx)"
    >
      <!-- Connector line -->
      <div
        v-if="idx > 0"
        class="tl-connector"
        :class="{ 'tl-connector-done': step.status === 'success' || step.status === 'degraded' }"
      />

      <!-- Step circle -->
      <div class="tl-circle">
        <div class="tl-circle-inner">
          <!-- Running spinner -->
          <svg
            v-if="step.status === 'running'"
            class="tl-spinner"
            viewBox="0 0 24 24"
          >
            <circle
              cx="12"
              cy="12"
              r="10"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
              stroke-dasharray="40 20"
              stroke-linecap="round"
            />
          </svg>
          <!-- Success checkmark -->
          <svg
            v-else-if="step.status === 'success'"
            class="tl-check"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="6 12 10 16 18 8" />
          </svg>
          <!-- Degraded warning -->
          <span
            v-else-if="step.status === 'degraded'"
            class="tl-degraded-icon"
          >!</span>
          <!-- Failed cross -->
          <svg
            v-else-if="step.status === 'failed'"
            class="tl-cross"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="3"
            stroke-linecap="round"
          >
            <line
              x1="8"
              y1="8"
              x2="16"
              y2="16"
            />
            <line
              x1="16"
              y1="8"
              x2="8"
              y2="16"
            />
          </svg>
          <!-- Waiting or step number -->
          <span
            v-else
            class="tl-number"
          >{{ step.step }}</span>
        </div>
      </div>

      <!-- Step content -->
      <div class="tl-content">
        <div class="tl-label">
          <span class="tl-icon">{{ stepIcons[step.step] }}</span>
          <span class="tl-name">{{ step.name }}</span>
        </div>
        <div
          v-if="step.duration_ms"
          class="tl-duration"
        >
          {{ formatDuration(step.duration_ms) }}
        </div>
        <div
          v-if="step.warning"
          class="tl-warning"
        >
          ⚠ {{ step.warning }}
        </div>
        <div
          v-if="step.error"
          class="tl-error"
        >
          ✕ {{ step.error }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loop-timeline {
  display: flex;
  align-items: flex-start;
  gap: 0;
  padding: var(--space-4) 0;
  overflow-x: auto;
}

.tl-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  min-width: 120px;
  position: relative;
  text-align: center;
}

.tl-clickable {
  cursor: pointer;
}

/* ── Connector line ── */
.tl-connector {
  position: absolute;
  top: 22px;
  right: 50%;
  width: 100%;
  height: 2px;
  background: var(--border);
  z-index: 0;
  transition: background 0.5s ease;
}
.tl-connector-done {
  background: linear-gradient(90deg, var(--success), var(--success));
}

/* ── Circle ── */
.tl-circle {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  transition: all 0.4s var(--ease-out);
  position: relative;
}

.tl-circle-inner {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2.5px solid var(--border);
  background: var(--card);
  transition: all 0.4s var(--ease-out);
}

/* Waiting */
.status-waiting .tl-circle-inner {
  border-color: var(--border);
  background: var(--card);
  opacity: 0.5;
}
.status-waiting .tl-number {
  color: var(--muted-foreground);
}

/* Running */
.status-running .tl-circle-inner {
  border-color: var(--primary);
  background: color-mix(in srgb, var(--primary) 8%, var(--card));
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--primary) 15%, transparent);
}
.tl-spinner {
  width: 24px;
  height: 24px;
  color: var(--primary);
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Success */
.status-success .tl-circle-inner {
  border-color: var(--success);
  background: color-mix(in srgb, var(--success) 10%, var(--card));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--success) 12%, transparent);
}
.tl-check {
  width: 22px;
  height: 22px;
  color: var(--success);
  animation: check-pop 0.35s var(--ease-out);
}
@keyframes check-pop {
  0% { transform: scale(0); opacity: 0; }
  60% { transform: scale(1.15); }
  100% { transform: scale(1); opacity: 1; }
}

/* Degraded */
.status-degraded .tl-circle-inner {
  border-color: var(--warning);
  background: color-mix(in srgb, var(--warning) 10%, var(--card));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--warning) 12%, transparent);
}
.tl-degraded-icon {
  font-size: var(--font-size-lg);
  font-weight: 800;
  color: var(--warning);
  line-height: 1;
}

/* Failed */
.status-failed .tl-circle-inner {
  border-color: var(--danger);
  background: color-mix(in srgb, var(--danger) 8%, var(--card));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--danger) 12%, transparent);
}
.tl-cross {
  width: 20px;
  height: 20px;
  color: var(--danger);
}

/* Number */
.tl-number {
  font-size: var(--font-size-sm);
  font-weight: 700;
  color: var(--foreground);
}

/* ── Content ── */
.tl-content {
  margin-top: var(--space-3);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
}

.tl-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
.tl-icon {
  font-size: 14px;
}
.tl-name {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--foreground);
  white-space: nowrap;
}
.tl-active .tl-name {
  color: var(--primary);
}

.tl-duration {
  font-size: 11px;
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

.tl-warning {
  font-size: 11px;
  color: var(--warning);
  font-weight: 500;
  max-width: 140px;
  text-align: center;
  line-height: 1.3;
}

.tl-error {
  font-size: 11px;
  color: var(--danger);
  font-weight: 500;
  max-width: 140px;
  text-align: center;
  line-height: 1.3;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .loop-timeline {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-3);
  }
  .tl-step {
    flex-direction: row;
    text-align: left;
    min-width: unset;
    gap: var(--space-3);
  }
  .tl-connector {
    display: none;
  }
  .tl-content {
    margin-top: 0;
    align-items: flex-start;
  }
}
</style>
