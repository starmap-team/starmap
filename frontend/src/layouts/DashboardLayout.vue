<script setup lang="ts">
/**
 * 数据大屏专用布局 — 全屏暗色主题
 * 无侧边栏，无面包屑，深色背景，沉浸式体验
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { FullScreen, Back } from '@element-plus/icons-vue'

const props = defineProps<{
  title?: string
  subtitle?: string
  clockTick?: number
  stale?: boolean
  staleSince?: number | string
}>()

const router = useRouter()
const isFullscreen = ref(false)

// Local fallback tick when no clockTick prop is provided
const localTick = ref(0)
let localTickTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  if (props.clockTick === undefined) {
    localTickTimer = setInterval(() => {
      localTick.value++
    }, 1000)
  }
})

onBeforeUnmount(() => {
  if (localTickTimer) {
    clearInterval(localTickTimer)
    localTickTimer = null
  }
})

const displayTime = computed(() => {
  // Access reactive tick so Vue re-evaluates every second
  void (props.clockTick !== undefined ? props.clockTick : localTick.value)
  const now = new Date()
  const y = now.getFullYear()
  const M = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  const h = String(now.getHours()).padStart(2, '0')
  const m = String(now.getMinutes()).padStart(2, '0')
  const s = String(now.getSeconds()).padStart(2, '0')
  return `${y}/${M}/${d} ${h}:${m}:${s}`
})

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
  }
}

const _fullscreenHandler = () => {
  isFullscreen.value = Boolean(document.fullscreenElement)
}
document.addEventListener('fullscreenchange', _fullscreenHandler)

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', _fullscreenHandler)
})

function goBack() {
  router.push('/')
}
</script>

<template>
  <div class="dashboard-layout">
    <!-- Top bar -->
    <header class="dashboard-header">
      <div class="header-left">
        <button
          class="header-btn back-btn"
          title="返回主页"
          @click="goBack"
        >
          <el-icon :size="16">
            <Back />
          </el-icon>
        </button>
        <div class="header-title-group">
          <h1 class="header-title">
            <span class="title-glow">{{ title || 'StarMap 数据大屏' }}</span>
          </h1>
          <span
            v-if="subtitle"
            class="header-subtitle"
          >{{ subtitle }}</span>
        </div>
      </div>
      <div class="header-right">
        <span
          v-if="stale"
          class="freshness-indicator stale"
        >⚠ 数据过期</span>
        <span
          v-else-if="stale === false"
          class="freshness-indicator fresh"
        >数据实时</span>
        <div class="header-time">
          {{ displayTime }}
        </div>
        <button
          class="header-btn"
          title="全屏"
          @click="toggleFullscreen"
        >
          <el-icon :size="16">
            <FullScreen />
          </el-icon>
        </button>
      </div>
    </header>

    <!-- Content -->
    <main class="dashboard-main">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.dashboard-layout {
  min-height: 100vh;
  width: 100%;
  background: var(--card);
  color: var(--foreground);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Header ── */
.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: linear-gradient(180deg, var(--dash-header-start) 0%, var(--dash-header-end) 100%);
  border-bottom: 1px solid color-mix(in srgb, var(--chart-1) 15%, transparent);
  backdrop-filter: blur(12px);
  z-index: 10;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title-group {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.header-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.title-glow {
  background: linear-gradient(135deg, var(--chart-1) 0%, var(--chart-3) 50%, var(--success) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-shadow: none;
  filter: drop-shadow(0 0 8px var(--dash-accent-30));
}

.header-subtitle {
  font-size: 12px;
  color: var(--dash-text-50);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.freshness-indicator {
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

.freshness-indicator.stale {
  color: var(--warning);
}

.freshness-indicator.fresh {
  color: var(--success);
  opacity: 0.6;
}

.header-time {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  color: var(--dash-text-60);
  font-family: 'JetBrains Mono', 'SF Mono', 'Cascadia Code', monospace;
}

.header-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--dash-accent-20);
  background: var(--dash-accent-5);
  border-radius: 6px;
  color: var(--dash-text-70);
  cursor: pointer;
  transition: all 0.2s ease;
}

.header-btn:hover {
  background: var(--dash-accent-15);
  border-color: var(--dash-accent-40);
  color: var(--chart-1);
  box-shadow: 0 0 12px var(--dash-accent-20);
}

.back-btn {
  width: 28px;
  height: 28px;
}

/* ── Main Content ── */
.dashboard-main {
  flex: 1;
  padding: 16px 20px 20px;
  overflow-y: auto;
  overflow-x: hidden;
}

/* Scrollbar styling */
.dashboard-main::-webkit-scrollbar {
  width: 6px;
}
.dashboard-main::-webkit-scrollbar-track {
  background: transparent;
}
.dashboard-main::-webkit-scrollbar-thumb {
  background: var(--dash-accent-20);
  border-radius: 3px;
}
.dashboard-main::-webkit-scrollbar-thumb:hover {
  background: var(--dash-accent-40);
}
</style>
