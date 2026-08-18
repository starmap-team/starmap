<script setup lang="ts">
/**
 * ErrorBoundary — catches child component errors and displays a fallback UI.
 *
 * Uses Vue 3's onErrorCaptured to intercept errors from descendant components.
 * The "retry" button resets the error state so the slot re-renders.
 */
import { ref, onErrorCaptured } from 'vue'

const hasError = ref(false)
const errorMessage = ref('')

onErrorCaptured((err, instance, info) => {
  hasError.value = true
  errorMessage.value = err.message || String(err)
  console.error('[ErrorBoundary] Caught error:', err)
  console.error('[ErrorBoundary] Stack:', err instanceof Error ? err.stack : 'N/A')
  console.error('[ErrorBoundary] Component:', instance?.$options?.name ?? instance?.$options?.__name ?? 'unknown')
  console.error('[ErrorBoundary] Info:', info)
  return false
})

function retry() {
  hasError.value = false
  errorMessage.value = ''
}
</script>

<template>
  <slot v-if="!hasError" />
  <div
    v-else
    class="error-boundary"
  >
    <div class="error-boundary-icon">
      <svg
        width="48"
        height="48"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle
          cx="12"
          cy="12"
          r="10"
        />
        <line
          x1="12"
          y1="8"
          x2="12"
          y2="12"
        />
        <line
          x1="12"
          y1="16"
          x2="12.01"
          y2="16"
        />
      </svg>
    </div>
    <h3 class="error-boundary-title">
      页面出现错误
    </h3>
    <p class="error-boundary-message">
      {{ errorMessage }}
    </p>
    <button
      class="error-boundary-retry"
      @click="retry"
    >
      重试
    </button>
  </div>
</template>

<style scoped>
.error-boundary {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10, 2.5rem) var(--space-6, 1.5rem);
  text-align: center;
  gap: var(--space-3, 0.75rem);
  min-height: 200px;
}

.error-boundary-icon {
  color: var(--destructive, #dc2626);
  opacity: 0.6;
  margin-bottom: var(--space-2, 0.5rem);
}

.error-boundary-title {
  font-size: var(--font-size-lg, 1rem);
  font-weight: 700;
  color: var(--foreground, #0a0a0b);
  margin: 0;
}

.error-boundary-message {
  font-size: var(--font-size-sm, 0.8125rem);
  color: var(--muted-foreground, #6b7280);
  margin: 0;
  max-width: 480px;
  word-break: break-word;
}

.error-boundary-retry {
  margin-top: var(--space-2, 0.5rem);
  padding: var(--space-2, 0.5rem) var(--space-5, 1.25rem);
  font-size: var(--font-size-sm, 0.8125rem);
  font-weight: 500;
  color: var(--primary-foreground, #ffffff);
  background: var(--primary, #4f46e5);
  border: none;
  border-radius: var(--radius-lg, 0.625rem);
  cursor: pointer;
  transition: background var(--duration-fast, 150ms) var(--ease-out, cubic-bezier(0.16, 1, 0.3, 1));
}

.error-boundary-retry:hover {
  background: var(--primary-hover, #4338ca);
}

.error-boundary-retry:active {
  transform: scale(0.98);
}
</style>
