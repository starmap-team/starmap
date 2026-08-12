<script setup lang="ts">
/**
 * DashboardSkeleton — Loading skeleton for the data dashboard.
 * Shown while initial data is loading.
 * 2026-08-13 (deep-interview): 回归普通页面风格 — 用 --card/--border 令牌
 * 替代 --dash-* 沉浸式令牌，随亮暗主题自适应。
 */
</script>

<template>
  <div class="dashboard-skeleton">
    <!-- KPI row skeleton (8 cards, 4 cols × 2 rows) -->
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
  gap: var(--gap-md, 12px);
}

.skeleton-kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--gap-md, 12px);
}

.skeleton-middle-row,
.skeleton-bottom-row {
  display: grid;
  gap: var(--gap-md, 12px);
}

.skeleton-middle-row {
  grid-template-columns: 1fr 1.5fr 1fr;
}

.skeleton-bottom-row {
  grid-template-columns: 1.2fr 1fr 1fr;
}

.skeleton-kpi-card,
.skeleton-panel {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg, 8px);
  animation: skeleton-pulse 1.8s ease-in-out infinite;
}

.skeleton-kpi-card {
  height: 68px;
}

.skeleton-panel {
  height: 300px;
}

@keyframes skeleton-pulse {
  0%, 100% {
    opacity: 0.5;
  }
  50% {
    opacity: 0.9;
  }
}

/* ── Responsive（对齐 DataDashboard.vue 断点） ── */
@media (max-width: 1280px) {
  .skeleton-middle-row,
  .skeleton-bottom-row {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .skeleton-kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .skeleton-middle-row,
  .skeleton-bottom-row {
    grid-template-columns: 1fr;
  }
}
</style>
