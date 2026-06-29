<script setup lang="ts">
/**
 * 主布局：顶部导航 + 面包屑 + 内容区 + 页脚
 * 支持移动端响应式折叠菜单
 */
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Monitor, Connection, DataAnalysis, TrendCharts,
  Setting, Document, User, Fold, Expand, Sunny, MoonNight,
} from '@element-plus/icons-vue'

const route = useRoute()
const mobileMenuOpen = ref(false)
const sidebarCollapsed = ref(false)
const isDark = ref(localStorage.getItem('theme') === 'dark')

// Apply dark mode on mount
if (isDark.value) {
  document.documentElement.classList.add('dark')
}

function toggleDarkMode() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

const navItems = [
  { path: '/',              title: '全景图谱', icon: Connection },
  { path: '/positions',     title: '岗位列表', icon: User },
  { path: '/match',         title: '匹配诊断', icon: Monitor },
  { path: '/evolution',     title: '演化看板', icon: TrendCharts },
  { path: '/extract',       title: 'JD抽取',   icon: Document },
  { path: '/quality',       title: '图谱质量', icon: DataAnalysis },
  { path: '/admin',         title: '管理后台', icon: Setting },
]

const currentTitle = computed(() => {
  return navItems.find(i => i.path === route.path)?.title ?? '星图'
})

const breadcrumbs = computed(() => {
  const meta = route.meta as Record<string, any>
  if (meta?.breadcrumb?.length) return meta.breadcrumb as string[]
  return ['首页', currentTitle.value]
})

function toggleMobileMenu() {
  mobileMenuOpen.value = !mobileMenuOpen.value
}

function closeMobileMenu() {
  mobileMenuOpen.value = false
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}
</script>

<template>
  <el-container class="layout">
    <!-- 顶部导航 -->
    <el-header class="layout-header">
      <div class="header-inner">
        <!-- Logo -->
        <router-link
          to="/"
          class="logo"
          @click="closeMobileMenu"
        >
          <span class="logo-icon">✦</span>
          <span class="logo-text">星图 StarMap</span>
        </router-link>

        <!-- 桌面端菜单 -->
        <el-menu
          :default-active="route.path"
          mode="horizontal"
          background-color="transparent"
          text-color="rgba(255,255,255,0.82)"
          active-text-color="#ffd04b"
          router
          class="desktop-menu"
          @select="closeMobileMenu"
        >
          <el-menu-item
            v-for="item in navItems"
            :key="item.path"
            :index="item.path"
          >
            <el-icon style="margin-right: 6px">
              <component :is="item.icon" />
            </el-icon>
            {{ item.title }}
          </el-menu-item>
        </el-menu>

        <!-- 暗色模式切换 -->
        <el-tooltip :content="isDark ? '切换亮色模式' : '切换暗色模式'" placement="bottom">
          <button class="theme-toggle" @click="toggleDarkMode" :aria-label="isDark ? '亮色' : '暗色'">
            <el-icon :size="18"><component :is="isDark ? Sunny : MoonNight" /></el-icon>
          </button>
        </el-tooltip>

        <!-- 移动端汉堡按钮 -->
        <button
          class="mobile-toggle"
          :aria-label="mobileMenuOpen ? '关闭菜单' : '打开菜单'"
          @click="toggleMobileMenu"
        >
          <span :class="{ open: mobileMenuOpen }" />
          <span :class="{ open: mobileMenuOpen }" />
          <span :class="{ open: mobileMenuOpen }" />
        </button>
      </div>
    </el-header>

    <!-- 移动端下拉菜单 -->
    <transition name="slide-down">
      <div
        v-if="mobileMenuOpen"
        class="mobile-menu"
      >
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="mobile-menu-item"
          :class="{ active: route.path === item.path }"
          @click="closeMobileMenu"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          {{ item.title }}
        </router-link>
      </div>
    </transition>

    <!-- 面包屑导航 -->
    <div class="breadcrumb-bar">
      <div class="breadcrumb-inner">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item
            v-for="(crumb, idx) in breadcrumbs"
            :key="idx"
            :to="idx < breadcrumbs.length - 1 ? { path: '/' } : undefined"
          >
            {{ crumb }}
          </el-breadcrumb-item>
        </el-breadcrumb>
        <span class="breadcrumb-current">{{ currentTitle }}</span>
      </div>
    </div>

    <!-- 主内容 -->
    <el-main class="layout-main">
      <slot />
    </el-main>

    <!-- 页脚 -->
    <el-footer class="layout-footer">
      <div class="footer-inner">
        <span>© 2026 星图 StarMap · 人才能力星云导航系统</span>
        <span class="footer-divider">|</span>
        <span>{{ currentTitle }}</span>
      </div>
    </el-footer>
  </el-container>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  background: #f5f7fa;
}

/* ── Header ── */
.layout-header {
  background: linear-gradient(135deg, #001529 0%, #003060 100%);
  padding: 0 24px;
  height: 60px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}

.header-inner {
  display: flex;
  align-items: center;
  height: 100%;
  max-width: 1400px;
  margin: 0 auto;
}

/* Logo */
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  margin-right: 40px;
  flex-shrink: 0;
}

.logo-icon {
  font-size: 24px;
  color: #ffd04b;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 1px;
  white-space: nowrap;
}

/* 桌面菜单 */
.desktop-menu {
  flex: 1;
  border-bottom: none !important;
  background: transparent !important;
}

.desktop-menu .el-menu-item {
  border-bottom: 2px solid transparent !important;
  transition: border-color 0.3s;
  font-size: 15px;
}

.desktop-menu .el-menu-item:hover {
  background: rgba(255, 255, 255, 0.08) !important;
}

.desktop-menu .el-menu-item.is-active {
  border-bottom-color: #ffd04b !important;
}

/* 主题切换按钮 */
.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.1);
  border: none;
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  color: #ffd04b;
  transition: background 0.2s;
  margin-right: 12px;
}
.theme-toggle:hover {
  background: rgba(255,255,255,0.2);
}

/* 移动端按钮 */
.mobile-toggle {
  display: none;
  flex-direction: column;
  gap: 5px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  margin-left: auto;
}

.mobile-toggle span {
  display: block;
  width: 24px;
  height: 2px;
  background: #fff;
  border-radius: 2px;
  transition: all 0.3s;
}

.mobile-toggle span.open:nth-child(1) {
  transform: translateY(7px) rotate(45deg);
}
.mobile-toggle span.open:nth-child(2) {
  opacity: 0;
}
.mobile-toggle span.open:nth-child(3) {
  transform: translateY(-7px) rotate(-45deg);
}

/* 移动端菜单 */
.mobile-menu {
  background: #001529;
  display: flex;
  flex-direction: column;
  padding: 8px 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.mobile-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 20px;
  color: rgba(255, 255, 255, 0.82);
  text-decoration: none;
  border-radius: 8px;
  font-size: 15px;
  transition: background 0.2s;
}

.mobile-menu-item:hover,
.mobile-menu-item.active {
  background: rgba(255, 255, 255, 0.1);
  color: #ffd04b;
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.25s ease;
}
.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ── Breadcrumb Bar ── */
.breadcrumb-bar {
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  padding: 10px 24px;
}

.breadcrumb-inner {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.breadcrumb-current {
  font-size: 13px;
  color: #909399;
}

/* ── Main ── */
.layout-main {
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
  padding: 24px;
  min-height: calc(100vh - 60px - 48px - 42px);
}

/* ── Footer ── */
.layout-footer {
  background: #fff;
  border-top: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
}

.footer-inner {
  font-size: 13px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

.footer-divider {
  color: #dcdfe6;
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .layout-header {
    padding: 0 16px;
  }

  .desktop-menu {
    display: none !important;
  }

  .mobile-toggle {
    display: flex;
  }

  .logo-text {
    font-size: 15px;
  }

  .layout-main {
    padding: 16px 12px;
  }

  .breadcrumb-bar {
    padding: 8px 12px;
  }

  .footer-inner {
    font-size: 12px;
  }
}
</style>
