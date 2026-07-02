<script setup lang="ts">
/**
 * LoadingPulse — CSS-only pulsing dots animation
 * Used for loading states across the app.
 */
withDefaults(defineProps<{
  size?: 'small' | 'default' | 'large'
  color?: string
}>(), {
  size: 'default',
  color: '',
})
</script>

<template>
  <div
    class="loading-pulse"
    :class="`loading-pulse--${size}`"
    :style="color ? { '--pulse-color': color } : {}"
    role="status"
    aria-label="加载中"
  >
    <span class="pulse-dot pulse-dot--1" />
    <span class="pulse-dot pulse-dot--2" />
    <span class="pulse-dot pulse-dot--3" />
  </div>
</template>

<style scoped>
.loading-pulse {
  --pulse-color: var(--primary, #4f46e5);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* Size variants */
.loading-pulse--small { gap: 4px; }
.loading-pulse--large { gap: 8px; }

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--pulse-color);
  animation: pulseDotScale 1.2s ease-in-out infinite;
}

.loading-pulse--small .pulse-dot {
  width: 5px;
  height: 5px;
}

.loading-pulse--large .pulse-dot {
  width: 12px;
  height: 12px;
}

.pulse-dot--1 { animation-delay: 0ms; }
.pulse-dot--2 { animation-delay: 200ms; }
.pulse-dot--3 { animation-delay: 400ms; }

@keyframes pulseDotScale {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .pulse-dot {
    animation: none;
    opacity: 0.6;
  }
}
</style>
