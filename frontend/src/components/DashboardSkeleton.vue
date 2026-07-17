<script setup lang="ts">
/**
 * DashboardSkeleton — Loading skeleton for the data dashboard.
 * Shown while initial data is loading.
 */
</script>

<template>
  <div class="dashboard-skeleton">
    <!-- KPI row skeleton -->
    <div class="skeleton-kpi-row">
      <div
        v-for="i in 8"
        :key="`kpi-${i}`"
        class="skeleton-kpi-card"
        :style="{ animationDelay: `${i * 60}ms` }"
      />
    </div>

    <!-- Middle row skeleton -->
    <div class="skeleton-middle-row">
      <div class="skeleton-panel" />
      <div class="skeleton-panel skeleton-wide" />
      <div class="skeleton-panel" />
    </div>

    <!-- Bottom row skeleton -->
    <div class="skeleton-bottom-row">
      <div class="skeleton-panel" />
      <div class="skeleton-panel skeleton-narrow" />
      <div class="skeleton-panel" />
    </div>
  </div>
</template>

<style scoped>
.dashboard-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--gap-md, 14px);
  height: calc(100vh - 72px);
  min-height: 700px;
}

.skeleton-kpi-row {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: var(--gap-sm, 12px);
  flex-shrink: 0;
}

.skeleton-middle-row,
.skeleton-bottom-row {
  display: grid;
  gap: var(--gap-md, 14px);
  flex: 1;
  min-height: 0;
}

.skeleton-middle-row {
  grid-template-columns: 1fr 1.5fr 1fr;
}

.skeleton-bottom-row {
  grid-template-columns: 1.2fr 0.8fr 1fr;
}

.skeleton-kpi-card,
.skeleton-panel {
  background: var(--dash-surface);
  border: 1px solid var(--dash-accent-10);
  border-radius: var(--radius-lg, 8px);
  animation: skeleton-pulse 1.8s ease-in-out infinite;
  opacity: 0.6;
}

.skeleton-kpi-card {
  height: 68px;
}

.skeleton-panel {
  height: 100%;
}

@keyframes skeleton-pulse {
  0%, 100% {
    background: var(--dash-surface);
    opacity: 0.4;
  }
  50% {
    background: color-mix(in srgb, var(--chart-1) 6%, var(--dash-surface));
    opacity: 0.7;
  }
}

/* ── Responsive ── */
@media (max-width: 1600px) {
  .skeleton-kpi-row {
    grid-template-columns: repeat(4, 1fr);
  }
  .skeleton-middle-row,
  .skeleton-bottom-row {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 1024px) {
  .skeleton-kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .skeleton-middle-row,
  .skeleton-bottom-row {
    grid-template-columns: 1fr;
  }
}
</style>