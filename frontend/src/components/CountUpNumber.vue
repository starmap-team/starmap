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
// D8e fix: displayValue 初始值直接取 target（>0 时）——数据大屏 8 张 KPI 曾全 0：
// 动画依赖 IntersectionObserver + rAF，在嵌套滚动容器/后台 tab 永不触发，值卡 0。
// 现在 mount 即显示真实值，动画仅作视觉增强（值变化时）。
const displayValue = ref(props.target > 0 ? props.target : 0)
let animFrame: number | null = null
let hasTriggered = false

/** easeOutCubic */
function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

function animateCount(from: number, to: number) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    displayValue.value = to
    return
  }
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
 // D8e: 立即显示目标值（数据大屏 8 张 KPI 曾全 0 —— observer/rAF 在嵌套滚动
 // 容器/后台 tab 不触发，动画永不启动）。先显示正确值，再用 rAF 平滑动画增强。
  displayValue.value = props.target
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    triggerFlash()
    return
  }
  animateCount(0, props.target)
  triggerFlash()
}

// IntersectionObserver setup
let observer: IntersectionObserver | null = null

onMounted(() => {
  if (!elRef.value) return

 // D8e fix: 初始值已直接显示 target（>0），无需 rAF/observer。
 // observer 仅兜底 target 从 0 变为 >0 的场景（异步数据）。
  if (props.target > 0) {
    return
  }

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
 // D8e: 0.1 threshold + rootMargin 提前触发 —— 大屏 KPI 卡在首屏下方时
 // 0.3 阈值可能永不满足导致动画不启动（值卡 0）
    { threshold: 0.1, rootMargin: '50px' },
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
 // D8e fix: 数据异步到达时 observer 可能尚未触发（hasTriggered=false）→
 // 之前直接 return 导致 displayValue 永远卡在 0（数据大屏 8 张 KPI 全 0 bug）。
 // 未触发但 target 已有真实值 → 立即显示，不依赖滚动可见的 observer。
  if (!hasTriggered) {
    if (newVal > 0) {
      displayValue.value = newVal
      triggerFlash()
    }
    return
  }
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
