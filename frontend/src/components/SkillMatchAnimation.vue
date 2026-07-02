<script setup lang="ts">
/**
 * SkillMatchAnimation — Animated skill matching sequence
 * Shows skills one by one with match/no-match icons, progress bar,
 * and a particle burst on successful match.
 */
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'

export interface SkillMatchItem {
  name: string
  matched: boolean
  score?: number
}

const props = withDefaults(defineProps<{
  skills: SkillMatchItem[]
  autoPlay?: boolean
  interval?: number
}>(), {
  autoPlay: true,
  interval: 600,
})

const emit = defineEmits<{
  (e: 'complete'): void
  (e: 'skill-reveal', index: number, skill: SkillMatchItem): void
}>()

const revealedCount = ref(0)
const isPlaying = ref(false)
let playTimer: ReturnType<typeof setInterval> | null = null
const particleBursts = ref<{ id: number; x: number; y: number; color: string }[]>([])
let particleId = 0

const progressPercent = computed(() => {
  if (!props.skills.length) return 0
  return Math.round((revealedCount.value / props.skills.length) * 100)
})

const matchedCount = computed(() => {
  return props.skills.slice(0, revealedCount.value).filter(s => s.matched).length
})

const revealedSkills = computed(() => {
  return props.skills.slice(0, revealedCount.value)
})

function spawnParticles(el: HTMLElement, matched: boolean) {
  const rect = el.getBoundingClientRect()
  const container = el.closest('.skill-match-animation')
  if (!container) return
  const containerRect = container.getBoundingClientRect()

  const cx = rect.left - containerRect.left + rect.width / 2
  const cy = rect.top - containerRect.top + rect.height / 2

  const colors = matched
    ? ['#22c55e', '#059669', '#34d399', '#a7f3d0']
    : ['#dc2626', '#f87171', '#ef4444']

  const count = matched ? 8 : 4
  for (let i = 0; i < count; i++) {
    const angle = (Math.PI * 2 * i) / count
    const dist = 16 + Math.random() * 20
    const px = Math.cos(angle) * dist
    const py = Math.sin(angle) * dist

    const id = ++particleId
    particleBursts.value.push({
      id,
      x: cx + px,
      y: cy + py,
      color: colors[i % colors.length],
    })

    setTimeout(() => {
      particleBursts.value = particleBursts.value.filter(p => p.id !== id)
    }, 700)
  }
}

function revealNext() {
  if (revealedCount.value >= props.skills.length) {
    stop()
    emit('complete')
    return
  }
  const idx = revealedCount.value
  revealedCount.value++
  emit('skill-reveal', idx, props.skills[idx])

  nextTick(() => {
    const items = document.querySelectorAll('.sm-skill-item')
    const item = items[idx] as HTMLElement | undefined
    if (item) {
      spawnParticles(item, props.skills[idx].matched)
    }
  })
}

function play() {
  if (isPlaying.value) return
  isPlaying.value = true
  revealedCount.value = 0
  particleBursts.value = []

  // Reveal first immediately
  revealNext()

  playTimer = setInterval(() => {
    revealNext()
  }, props.interval)
}

function stop() {
  isPlaying.value = false
  if (playTimer) {
    clearInterval(playTimer)
    playTimer = null
  }
}

function reset() {
  stop()
  revealedCount.value = 0
  particleBursts.value = []
}

// Watch for skills change with autoPlay
watch(() => props.skills, (newSkills) => {
  if (newSkills.length && props.autoPlay) {
    reset()
    nextTick(() => play())
  }
}, { immediate: true })

onUnmounted(() => {
  stop()
})

defineExpose({ play, stop, reset })
</script>

<template>
  <div class="skill-match-animation">
    <!-- Progress bar -->
    <div class="sm-progress-bar">
      <div
        class="sm-progress-fill"
        :style="{ width: progressPercent + '%' }"
      />
      <span class="sm-progress-text">{{ progressPercent }}%</span>
    </div>

    <!-- Skill items -->
    <div class="sm-skills-list">
      <div
        v-for="(skill, idx) in skills"
        :key="skill.name"
        class="sm-skill-item"
        :class="{
          'sm-revealed': idx < revealedCount,
          'sm-matched': idx < revealedCount && skill.matched,
          'sm-unmatched': idx < revealedCount && !skill.matched,
        }"
      >
        <span class="sm-skill-icon">
          <template v-if="idx < revealedCount">
            <span v-if="skill.matched" class="sm-icon-match">&#10003;</span>
            <span v-else class="sm-icon-miss">&#10007;</span>
          </template>
          <template v-else>
            <span class="sm-icon-pending">&bull;</span>
          </template>
        </span>
        <span class="sm-skill-name">{{ skill.name }}</span>
        <span
          v-if="idx < revealedCount && skill.score !== undefined"
          class="sm-skill-score"
        >
          {{ Math.round(skill.score * 100) }}%
        </span>
      </div>
    </div>

    <!-- Matched count summary -->
    <div
      v-if="revealedCount > 0"
      class="sm-summary"
    >
      <span class="sm-summary-match">{{ matchedCount }}</span>
      <span class="sm-summary-sep">/</span>
      <span class="sm-summary-total">{{ skills.length }}</span>
      <span class="sm-summary-label">项匹配</span>
    </div>

    <!-- Particle container -->
    <div class="sm-particles">
      <span
        v-for="p in particleBursts"
        :key="p.id"
        class="sm-particle"
        :style="{
          left: p.x + 'px',
          top: p.y + 'px',
          background: p.color,
        }"
      />
    </div>
  </div>
</template>

<style scoped>
.skill-match-animation {
  position: relative;
}

/* Progress bar */
.sm-progress-bar {
  height: 6px;
  background: var(--muted);
  border-radius: var(--radius-full);
  overflow: hidden;
  position: relative;
  margin-bottom: var(--space-4);
}

.sm-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--chart-2));
  border-radius: var(--radius-full);
  transition: width 0.4s var(--ease-out);
}

.sm-progress-text {
  position: absolute;
  right: 0;
  top: -20px;
  font-size: 11px;
  font-weight: 600;
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
}

/* Skills list */
.sm-skills-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sm-skill-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  opacity: 0;
  transform: translateX(-8px);
  transition: all 0.3s var(--ease-out);
  background: var(--card);
  border: 1px solid var(--border);
}

.sm-skill-item.sm-revealed {
  opacity: 1;
  transform: translateX(0);
}

.sm-skill-item.sm-matched {
  border-color: color-mix(in srgb, var(--success) 30%, var(--border));
  background: color-mix(in srgb, var(--success) 4%, var(--card));
}

.sm-skill-item.sm-unmatched {
  border-color: color-mix(in srgb, var(--destructive) 20%, var(--border));
  background: color-mix(in srgb, var(--destructive) 3%, var(--card));
}

/* Icons */
.sm-skill-icon {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 700;
  border-radius: 50%;
}

.sm-icon-match {
  color: #fff;
  background: var(--success);
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  animation: iconPop 0.3s var(--ease-spring) both;
}

.sm-icon-miss {
  color: #fff;
  background: var(--destructive);
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  animation: iconPop 0.3s var(--ease-spring) both;
}

.sm-icon-pending {
  color: var(--muted-foreground);
  font-size: 18px;
}

@keyframes iconPop {
  0% { transform: scale(0); }
  60% { transform: scale(1.2); }
  100% { transform: scale(1); }
}

.sm-skill-name {
  flex: 1;
  font-weight: 500;
  color: var(--foreground);
}

.sm-skill-score {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
}

/* Summary */
.sm-summary {
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
  margin-top: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
}

.sm-summary-match {
  font-size: var(--font-size-2xl);
  font-weight: 800;
  color: var(--success);
  line-height: 1;
}

.sm-summary-sep {
  font-weight: 300;
  margin: 0 2px;
}

.sm-summary-total {
  font-weight: 600;
}

.sm-summary-label {
  margin-left: var(--space-1);
}

/* Particles */
.sm-particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.sm-particle {
  position: absolute;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  animation: particleFly 0.6s var(--ease-out) forwards;
}

@keyframes particleFly {
  0% {
    opacity: 1;
    transform: scale(1);
  }
  100% {
    opacity: 0;
    transform: scale(0);
  }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .sm-skill-item {
    transition: none;
    opacity: 1;
    transform: none;
  }
  .sm-icon-match,
  .sm-icon-miss {
    animation: none;
  }
  .sm-particle {
    display: none;
  }
}
</style>
