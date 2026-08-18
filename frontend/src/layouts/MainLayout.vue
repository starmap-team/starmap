<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DataAnalysis, DataLine, Connection, TrendCharts, Document, Setting, User, Sunny, MoonNight, Fold, Expand, Coin, Refresh, Odometer, Reading } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import ProfileMenu from '@/components/ProfileMenu.vue'

const userStore = useUserStore()
userStore.initUser()

const route = useRoute()
const router = useRouter()
const mobileMenuOpen = ref(false)
const sidebarCollapsed = ref(false)
const isDark = ref(localStorage.getItem('theme') === 'dark')
if (isDark.value) document.documentElement.classList.add('dark')
function toggleDarkMode() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}
const baseNavItems = [
  { path: '/', title: '全景图谱', icon: Connection, group: 'data' },
  { path: '/positions', title: '岗位列表', icon: User, group: 'data' },
  { path: '/pipeline', title: '数据流水线', icon: DataLine, group: 'data' },
  { path: '/datasources', title: '数据源管理', icon: Coin, group: 'data' },
  { path: '/match', title: '匹配诊断', icon: DataAnalysis, group: 'tools' },
  { path: '/analysis', title: '求职者分析', icon: User, group: 'tools' },
  { path: '/extract', title: 'JD 抽取', icon: Document, group: 'tools' },
  { path: '/loop', title: '闭环演示', icon: Refresh, group: 'tools' },
  { path: '/learning', title: '学习中心', icon: Reading, group: 'tools' },
  { path: '/dashboard', title: '数据大屏', icon: Odometer, group: 'insight' },
  { path: '/evolution', title: '演化看板', icon: TrendCharts, group: 'insight' },
  { path: '/quality', title: '图谱质量', icon: DataAnalysis, group: 'insight' },
]
const adminNavItems = [
  { path: '/admin', title: '管理后台', icon: Setting, group: 'system' },
]
const navItems = computed(() => {
  if (userStore.isAdmin) {
    return [...baseNavItems, ...adminNavItems]
  }
  return baseNavItems
})
const navGroups = [
  { key: 'data', label: '数据' },
  { key: 'tools', label: '工具' },
  { key: 'insight', label: '洞察' },
  { key: 'system', label: '系统' },
]
// ponytail: 原精确匹配 route.path === item.path 导致详情页 /position/:name 丢菜单高亮与标题；
// 详情页归位到"岗位列表"
function isActiveItem(item: { path: string }): boolean {
  if (route.path === item.path) return true
  return item.path === '/positions' && route.path.startsWith('/position/')
}
const currentTitle = computed(() => navItems.value.find(i => isActiveItem(i))?.title ?? '星图')
const breadcrumbs = computed(() => {
  const meta = route.meta as Record<string, unknown>
  const bc = meta?.breadcrumb
  if (Array.isArray(bc) && bc.length) return bc as string[]
  return ['首页', currentTitle.value]
})
function closeMobileMenu() { mobileMenuOpen.value = false }
function navigateTo(path: string) { router.push(path); closeMobileMenu() }
watch(() => route.path, () => { mobileMenuOpen.value = false })
</script>

<template>
  <div
    class="layout"
    :class="{ 'sidebar-collapsed': sidebarCollapsed }"
  >
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <router-link
          to="/"
          class="sidebar-brand"
          @click="closeMobileMenu"
        >
          <div class="brand-mark">
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                cx="12"
                cy="12"
                r="3.5"
                fill="currentColor"
                opacity="0.9"
              />
              <circle
                cx="12"
                cy="12"
                r="7.5"
                stroke="currentColor"
                stroke-width="1.5"
                opacity="0.3"
                stroke-dasharray="2 3"
              />
              <circle
                cx="12"
                cy="12"
                r="11"
                stroke="currentColor"
                stroke-width="0.8"
                opacity="0.1"
              />
              <circle
                cx="5.5"
                cy="7.5"
                r="1.3"
                fill="currentColor"
                opacity="0.45"
              />
              <circle
                cx="18.5"
                cy="5.5"
                r="1"
                fill="currentColor"
                opacity="0.3"
              />
              <circle
                cx="17"
                cy="18"
                r="1.2"
                fill="currentColor"
                opacity="0.4"
              />
            </svg>
          </div>
          <div
            v-show="!sidebarCollapsed"
            class="brand-text-group"
          >
            <span class="brand-text">StarMap</span>
            <span class="brand-badge">星图</span>
          </div>
        </router-link>
      </div>
      <button
        class="sidebar-collapse-btn"
        :title="sidebarCollapsed ? '展开侧栏' : '折叠侧栏'"
        @click="sidebarCollapsed = !sidebarCollapsed"
      >
        <el-icon :size="16">
          <component :is="sidebarCollapsed ? Expand : Fold" />
        </el-icon>
      </button>

      <nav class="sidebar-nav">
        <div
          v-for="group in navGroups"
          :key="group.key"
          class="nav-group"
        >
          <span
            v-show="!sidebarCollapsed"
            class="nav-group-label"
          >{{ group.label }}</span>
          <div
            v-for="item in navItems.filter(i => i.group === group.key)"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActiveItem(item) }"
            @click="navigateTo(item.path)"
          >
            <div class="nav-item-icon">
              <el-icon :size="18">
                <component :is="item.icon" />
              </el-icon>
            </div>
            <span
              v-show="!sidebarCollapsed"
              class="nav-item-label"
            >{{ item.title }}</span>
            <div
              v-if="isActiveItem(item)"
              class="nav-item-indicator"
            />
          </div>
        </div>
      </nav>

      <div class="sidebar-footer">
        <button
          class="sidebar-action"
          :title="isDark ? '浅色模式' : '深色模式'"
          @click="toggleDarkMode"
        >
          <el-icon :size="16">
            <component :is="isDark ? Sunny : MoonNight" />
          </el-icon>
          <span v-show="!sidebarCollapsed">{{ isDark ? '浅色模式' : '深色模式' }}</span>
        </button>
      </div>
    </aside>

    <!-- Mobile Header -->
    <header class="mobile-header">
      <button
        class="mobile-toggle"
        aria-label="菜单"
        @click="mobileMenuOpen = !mobileMenuOpen"
      >
        <span :class="{ open: mobileMenuOpen }" /><span :class="{ open: mobileMenuOpen }" /><span :class="{ open: mobileMenuOpen }" />
      </button>
      <router-link
        to="/"
        class="mobile-brand"
        @click="closeMobileMenu"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
        >
          <circle
            cx="12"
            cy="12"
            r="3.5"
            fill="currentColor"
            opacity="0.9"
          />
          <circle
            cx="12"
            cy="12"
            r="7.5"
            stroke="currentColor"
            stroke-width="1.5"
            opacity="0.3"
            stroke-dasharray="2 3"
          />
        </svg>
        <span style="font-weight:700;font-size:var(--font-size-sm);letter-spacing:-0.02em">StarMap</span>
      </router-link>
      <button
        class="action-btn"
        @click="toggleDarkMode"
      >
        <el-icon :size="16">
          <component :is="isDark ? Sunny : MoonNight" />
        </el-icon>
      </button>
    </header>

    <!-- Mobile Menu -->
    <transition name="slide-down">
      <div
        v-if="mobileMenuOpen"
        class="mobile-menu glass"
      >
        <div
          v-for="item in navItems"
          :key="item.path"
          class="mobile-link"
          :class="{ active: isActiveItem(item) }"
          @click="navigateTo(item.path)"
        >
          <el-icon :size="18">
            <component :is="item.icon" />
          </el-icon>
          <span>{{ item.title }}</span>
        </div>
      </div>
    </transition>

    <!-- Main Content -->
    <div class="main-wrapper">
      <div class="topbar">
        <div class="topbar-spacer" />
        <ProfileMenu v-if="userStore.isLoggedIn" />
      </div>
      <div class="breadcrumb-bar">
        <div class="breadcrumbs">
          <template
            v-for="(bc, idx) in breadcrumbs"
            :key="idx"
          >
            <span
              v-if="idx > 0"
              class="bc-sep"
            >/</span>
            <span :class="idx === breadcrumbs.length - 1 ? 'bc-current' : 'bc-item'">{{ bc }}</span>
          </template>
        </div>
      </div>
      <main class="layout-main">
        <slot />
      </main>
      <footer class="layout-footer">
        <span>StarMap · 人才能力星云导航系统</span>
        <span class="footer-sep">|</span>
        <span>XH-202621</span>
      </footer>
    </div>
  </div>
</template>

<style>
/* fix: extract scoped styles to external file */
@import './MainLayout.css';
</style>

