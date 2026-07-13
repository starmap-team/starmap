<script setup lang="ts">
/**
 * SkeletonCard — animated skeleton placeholder for loading states.
 *
 * Renders a configurable number of animated lines to indicate content loading.
 * Uses the global .skeleton CSS animation defined in App.vue.
 */
withDefaults(defineProps<{
  lines?: number
}>(), {
  lines: 3,
})
</script>

<template>
  <div class="skeleton-card">
    <!-- Header line (wider) -->
    <div
      class="skeleton skeleton-line skeleton-header"
    />
    <!-- Body lines -->
    <div
      v-for="i in lines"
      :key="i"
      class="skeleton skeleton-line"
      :style="{
        width: i === lines ? '40%' : `${70 + Math.sin(i) * 20}%`,
        animationDelay: `${i * 0.1}s`,
      }"
    />
  </div>
</template>

<style scoped>
.skeleton-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3, 0.75rem);
  padding: var(--space-5, 1rem);
  background: var(--card, #ffffff);
  border: 1px solid var(--border, #e5e7eb);
  border-radius: var(--radius-xl, 0.625rem);
}

.skeleton-line {
  height: 14px;
  border-radius: var(--radius-md, 0.5rem);
}

.skeleton-header {
  height: 18px;
  width: 55%;
}
</style>
