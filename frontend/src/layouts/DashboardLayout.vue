<script setup lang="ts">
/**
 * 数据大屏专用布局 — 全屏暗色主题
 * 无侧边栏，无面包屑，深色背景，沉浸式体验
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { FullScreen, RefreshRight, Back } from '@element-plus/icons-vue'

defineProps<{
  title?: string
  subtitle?: string
}>()

const router = useRouter()
const isFullscreen = ref(false)

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
  }
}

document.addEventListener('fullscreenchange', () => {
  isFullscreen.value = !!document.fullscreenElement
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
        <div class="header-time">
          {{ new Date().toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) }}
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
  background: #0a0a1a;
  color: #e0e6ed;
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
  background: linear-gradient(180deg, rgba(10, 10, 26, 0.95) 0%, rgba(10, 10, 26, 0.7) 100%);
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
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
  background: linear-gradient(135deg, #00d4ff 0%, #7b61ff 50%, #00ff88 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-shadow: none;
  filter: drop-shadow(0 0 8px rgba(0, 212, 255, 0.3));
}

.header-subtitle {
  font-size: 12px;
  color: rgba(224, 230, 237, 0.5);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-time {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  color: rgba(224, 230, 237, 0.6);
  font-family: 'JetBrains Mono', 'SF Mono', 'Cascadia Code', monospace;
}

.header-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid rgba(0, 212, 255, 0.2);
  background: rgba(0, 212, 255, 0.05);
  border-radius: 6px;
  color: rgba(224, 230, 237, 0.7);
  cursor: pointer;
  transition: all 0.2s ease;
}

.header-btn:hover {
  background: rgba(0, 212, 255, 0.15);
  border-color: rgba(0, 212, 255, 0.4);
  color: #00d4ff;
  box-shadow: 0 0 12px rgba(0, 212, 255, 0.2);
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
  background: rgba(0, 212, 255, 0.2);
  border-radius: 3px;
}
.dashboard-main::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 212, 255, 0.4);
}
</style>
