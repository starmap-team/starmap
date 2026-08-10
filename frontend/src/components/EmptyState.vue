<script setup lang="ts">
/**
 * EmptyState — shared empty state placeholder component.
 *
 * Displays a centered icon + title + description when there is no data.
 * Used across pages: DataDashboard, LearningCenter, EvolutionDashboard, etc.
 */
withDefaults(defineProps<{
  title: string
  description?: string
  icon?: string
}>(), {
  description: '',
  icon: '',
})
</script>

<template>
  <div class="empty-state">
    <span
      v-if="icon"
      class="empty-state-icon"
    >{{ icon }}</span>
    <div
      v-else
      class="empty-state-icon-svg"
    >
      <svg
        width="48"
        height="48"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M3 3v18h18" />
        <path d="m19 9-5 5-4-4-3 3" />
      </svg>
    </div>
    <p class="empty-state-title">
      {{ title }}
    </p>
    <p
      v-if="description"
      class="empty-state-desc"
    >
      {{ description }}
    </p>
    <!-- 10-03 (D-12): 引导 slot — 空态可放 CTA 按钮（触发演化分析/查看文档），
         无 slot 时保持既有纯文本空态，向后兼容 -->
    <div
      v-if="$slots.default"
      class="empty-state-actions"
    >
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10, 2.5rem) var(--space-6, 1.5rem);
  text-align: center;
  gap: var(--space-2, 0.5rem);
}

.empty-state-icon {
  font-size: 28px;
  opacity: 0.35;
  line-height: 1;
  margin-bottom: var(--space-1, 0.25rem);
}

.empty-state-icon-svg {
  color: var(--muted-foreground, #6b7280);
  opacity: 0.35;
  margin-bottom: var(--space-1, 0.25rem);
}

.empty-state-title {
  font-size: var(--font-size-base, 0.875rem);
  font-weight: 600;
  color: var(--foreground, #0a0a0b);
  margin: 0;
}

.empty-state-desc {
  font-size: var(--font-size-sm, 0.8125rem);
  color: var(--muted-foreground, #6b7280);
  margin: 0;
  max-width: 360px;
}

.empty-state-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3, 0.75rem);
  flex-wrap: wrap;
  margin-top: var(--space-1, 0.25rem);
}
</style>
