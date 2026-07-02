<script setup lang="ts">
/**
 * CountUpNumber — Animated number counter with visibility trigger
 * Uses IntersectionObserver + requestAnimationFrame for performant animation.
 * Supports formatted numbers (locale separators), prefix, suffix, decimals.
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

const props = withDefaults(defineProps<{
  target: number
  duration?: number
  prefix?: string
  suffix?: string
  decimals?: number
}>(), {
  duration: 1200,
  prefix: '',
  suffix: '',
  decimals: 0,
})

const elRef = ref<HTMLElement | null>(null)
const displayValue = ref(0)
let animFrame: number | null = null
let hasTriggered = false

/** easeOutCubic */
function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

function animateCount(from: number, to: number) {
  if (animFrame) cancelAnimationFrame(animFrame)
  const start = performance.now()
  const diff = to - from

  function step(now: number) {
    const elapsed = now - start
    const progress = Math.min(elapsed / props.duration, 1)
    const eased = easeOutCubic(progress)
    displayValue.value = from + diff * eased

    if (progress < 1) {
      animFrame = requestAnimationFrame(step)
    } else {
      displayValue.value = to
    }
  }

  animFrame = requestAnimationFrame(step)
}

/** Format number with locale separators and decimals */
const formattedNumber = computed(() => {
  const val = displayValue.value
  if (props.decimals > 0) {
    return val.toFixed(props.decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  }
  return Math.round(val).toLocaleString()
})

const displayText = computed(() => {
  return `${props.prefix}${formattedNumber.value}${props.suffix}`
})

/** Flash class when value changes */
const isFlashing = ref(false)
let flashTimer: ReturnType<typeof setTimeout> | null = null

function triggerFlash() {
  isFlashing.value = true
  if (flashTimer) clearTimeout(flashTimer)
  flashTimer = setTimeout(() => {
    isFlashing.value = false
  }, 700)
}

/** Start animation when visible */
function startCountUp() {
  if (hasTriggered) return
  hasTriggered = true
  animateCount(0, props.target)
  triggerFlash()
}

// IntersectionObserver setup
let observer: IntersectionObserver | null = null

onMounted(() => {
  if (!elRef.value) return

  // Check if IntersectionObserver is available
  if (typeof IntersectionObserver === 'undefined') {
    startCountUp()
    return
  }

  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          startCountUp()
          observer?.disconnect()
          break
        }
      }
    },
    { threshold: 0.3 },
  )

  observer.observe(elRef.value)
})

onUnmounted(() => {
  if (animFrame) cancelAnimationFrame(animFrame)
  if (flashTimer) clearTimeout(flashTimer)
  observer?.disconnect()
})

/** Re-animate when target changes */
watch(() => props.target, (newVal, oldVal) => {
  if (!hasTriggered) return
  const from = oldVal ?? 0
  animateCount(from, newVal)
  triggerFlash()
})
</script>

<template>
  <span
    ref="elRef"
    class="count-up-number"
    :class="{ 'count-up-flash': isFlashing }"
  >
    {{ displayText }}
  </span>
</template>

<style scoped>
.count-up-number {
  display: inline-block;
  font-variant-numeric: tabular-nums;
  transition: text-shadow 0.3s var(--ease-out);
}

.count-up-flash {
  animation: countFlash 0.7s var(--ease-out) both;
}

@keyframes countFlash {
  0% {
    text-shadow: 0 0 0 transparent;
  }
  30% {
    text-shadow: 0 0 12px currentColor;
  }
  100% {
    text-shadow: 0 0 0 transparent;
  }
}
</style>
