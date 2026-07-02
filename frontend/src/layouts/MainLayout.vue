<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DataAnalysis, DataLine, Connection, TrendCharts, Document, Setting, User, Sunny, MoonNight, Fold, Expand, Coin, Refresh, Odometer, Reading } from '@element-plus/icons-vue'
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
const navItems = [
  { path: '/', title: '全景图谱', icon: Connection, group: 'data' },
  { path: '/positions', title: '岗位列表', icon: User, group: 'data' },
  { path: '/pipeline', title: '数据流水线', icon: DataLine, group: 'data' },
  { path: '/datasources', title: '数据源管理', icon: Coin, group: 'data' },
  { path: '/match', title: '匹配诊断', icon: DataAnalysis, group: 'tools' },
  { path: '/extract', title: 'JD 抽取', icon: Document, group: 'tools' },
  { path: '/loop', title: '闭环演示', icon: Refresh, group: 'tools' },
  { path: '/learning', title: '学习中心', icon: Reading, group: 'tools' },
  { path: '/dashboard', title: '数据大屏', icon: Odometer, group: 'insight' },
  { path: '/evolution', title: '演化看板', icon: TrendCharts, group: 'insight' },
  { path: '/quality', title: '图谱质量', icon: DataAnalysis, group: 'insight' },
  { path: '/admin', title: '管理后台', icon: Setting, group: 'system' },
]
const navGroups = [
  { key: 'data', label: '数据' },
  { key: 'tools', label: '工具' },
  { key: 'insight', label: '洞察' },
  { key: 'system', label: '系统' },
]
const currentTitle = computed(() => navItems.find(i => i.path === route.path)?.title ?? '星图')
const breadcrumbs = computed(() => {
  const meta = route.meta as Record<string, any>
  if (meta?.breadcrumb?.length) return meta.breadcrumb as string[]
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
            :class="{ active: route.path === item.path }"
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
              v-if="route.path === item.path"
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
          :class="{ active: route.path === item.path }"
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

<style scoped>
/* Sidebar */
.sidebar {
  position: fixed;
  top: 0; left: 0; bottom: 0;
  width: var(--sidebar-width);
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  z-index: var(--z-sticky);
  transition: width var(--duration-slow) var(--ease-out), background var(--duration-normal), box-shadow var(--duration-normal);
  overflow: hidden;
  box-shadow: var(--shadow-sidebar, 2px 0 12px rgba(0,0,0,0.04));
}
.sidebar-collapsed .sidebar { width: var(--sidebar-width-collapsed); }

.sidebar-header {
  padding: var(--space-5) var(--space-4);
  flex-shrink: 0;
}
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  text-decoration: none;
  color: var(--foreground);
  padding: var(--space-2) var(--space-2);
  border-radius: var(--radius-lg);
  transition: all var(--duration-fast);
}
.sidebar-brand:hover { background: var(--sidebar-hover); }
.sidebar-brand:hover .brand-mark { color: var(--primary); }
.brand-mark {
  color: var(--muted-foreground);
  transition: color var(--duration-fast);
  flex-shrink: 0;
  display: flex;
  align-items: center;
}
.brand-text-group {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  min-width: 0;
}
.brand-text {
  font-size: var(--font-size-lg);
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--foreground);
}
.brand-badge {
  font-size: 10px;
  font-weight: 500;
  color: var(--muted-foreground);
  background: var(--muted);
  padding: 1px 6px;
  border-radius: var(--radius-full);
  letter-spacing: 0.02em;
}

/* Nav */
.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2) var(--space-3);
}
.nav-group { margin-bottom: var(--space-4); }
.nav-group-label {
  display: block;
  font-size: 10px;
  font-weight: 700;
  color: var(--muted-foreground);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  padding: var(--space-2) var(--space-3) var(--space-1);
  margin-bottom: var(--space-1);
  position: relative;
}
.nav-group-label::after {
  content: '';
  display: block;
  width: 16px;
  height: 2px;
  background: color-mix(in srgb, var(--muted-foreground) 25%, transparent);
  border-radius: 1px;
  margin-top: 4px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
  font-weight: 500;
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  white-space: nowrap;
  margin-bottom: 2px;
}
.nav-item:hover { color: var(--foreground); background: var(--sidebar-hover); }
.nav-item:hover .nav-item-icon {
  transform: scale(1.12);
  color: var(--foreground);
}
.nav-item.active {
  color: var(--primary);
  background: var(--sidebar-active);
  font-weight: 600;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--primary) 10%, transparent),
              inset 0 0 12px color-mix(in srgb, var(--primary) 4%, transparent);
}
.nav-item.active .nav-item-icon {
  color: var(--primary);
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--primary) 40%, transparent));
}
.nav-item-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  flex-shrink: 0;
  transition: transform var(--duration-fast) var(--ease-spring),
              color var(--duration-fast),
              filter var(--duration-fast);
}
.nav-item-label { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.nav-item-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--primary);
  border-radius: 0 3px 3px 0;
  box-shadow: 0 0 8px color-mix(in srgb, var(--primary) 50%, transparent);
  animation: indicator-enter 0.25s var(--ease-spring) both;
}
@keyframes indicator-enter {
  from {
    height: 0;
    opacity: 0;
  }
  to {
    height: 20px;
    opacity: 1;
  }
}

/* Footer */
.sidebar-footer {
  padding: var(--space-3);
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.sidebar-action {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: none;
  background: none;
  border-radius: var(--radius-md);
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast);
  white-space: nowrap;
}
.sidebar-action:hover { color: var(--foreground); background: var(--sidebar-hover); }

/* Main Wrapper */
.main-wrapper {
  flex: 1;
  margin-left: var(--sidebar-width);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  transition: margin-left var(--duration-slow) var(--ease-out);
}
.sidebar-collapsed .main-wrapper { margin-left: var(--sidebar-width-collapsed); }

/* Mobile Header */
.mobile-header {
  display: none;
  align-items: center;
  gap: var(--space-3);
  height: var(--header-height);
  padding: 0 var(--space-4);
  background: color-mix(in srgb, var(--card) 85%, transparent);
  backdrop-filter: blur(16px) saturate(1.8);
  -webkit-backdrop-filter: blur(16px) saturate(1.8);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
}
.mobile-brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  text-decoration: none;
  color: var(--foreground);
}
.mobile-toggle {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 6px;
  border: none;
  background: none;
  cursor: pointer;
}
.mobile-toggle span {
  display: block;
  width: 18px;
  height: 2px;
  background: var(--foreground);
  border-radius: 1px;
  transition: all var(--duration-normal) var(--ease-out);
}
.mobile-toggle span.open:nth-child(1) { transform: translateY(7px) rotate(45deg); }
.mobile-toggle span.open:nth-child(2) { opacity: 0; }
.mobile-toggle span.open:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }
.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px; height: 34px;
  border: none;
  background: none;
  border-radius: var(--radius-md);
  color: var(--muted-foreground);
  cursor: pointer;
  transition: all var(--duration-fast);
  margin-left: auto;
}
.action-btn:hover { color: var(--foreground); background: var(--accent); }

/* Mobile Menu */
.mobile-menu {
  position: fixed;
  top: var(--header-height);
  left: 0; right: 0;
  z-index: var(--z-dropdown);
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--border);
}
.mobile-link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  color: var(--foreground);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--duration-fast);
}
.mobile-link:hover, .mobile-link.active { background: var(--primary-ghost); color: var(--primary); }
.slide-down-enter-active, .slide-down-leave-active { transition: all var(--duration-normal) var(--ease-out); }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-8px); }

/* Breadcrumb */
.breadcrumb-bar {
  padding: var(--space-3) var(--space-6);
  border-bottom: 1px solid var(--border);
  background: var(--card);
}
.breadcrumbs {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}
.bc-sep { color: var(--border); }
.bc-item { color: var(--muted-foreground); }
.bc-current { color: var(--foreground); font-weight: 500; }

/* Content */
.layout-main {
  flex: 1;
  max-width: var(--content-max-width);
  width: 100%;
  margin: 0 auto;
  padding: var(--space-6);
}

/* Footer */
.layout-footer {
  border-top: 1px solid var(--border);
  padding: var(--space-5) var(--space-6);
  text-align: center;
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}
.footer-sep { color: var(--border); }

/* Collapsed sidebar */
.sidebar-collapsed .sidebar-nav { padding: var(--space-1) var(--space-1); }
.sidebar-collapsed .nav-item { justify-content: center; padding: var(--space-2); }
.sidebar-collapsed .nav-item:hover .nav-item-icon { transform: scale(1.18); }
.sidebar-collapsed .nav-item.active { box-shadow: 0 0 0 1px color-mix(in srgb, var(--primary) 12%, transparent); }
.sidebar-collapsed .nav-group-label { display: none; }
.sidebar-collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  color: var(--muted-foreground);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  flex-shrink: 0;
  opacity: 0.5;
  margin: 0 var(--space-3) var(--space-2) auto;
}
.sidebar-collapse-btn:hover {
  opacity: 1;
  color: var(--foreground);
  background: var(--sidebar-hover);
  transform: scale(1.08);
}
.sidebar-collapse-btn:active {
  transform: scale(0.95);
}

html.dark .sidebar { background: var(--card); }

/* Responsive */
@media (max-width: 1024px) {
  .sidebar { display: none; }
  .main-wrapper { margin-left: 0; }
  .mobile-header { display: flex; }
  .breadcrumb-bar { padding: var(--space-2) var(--space-4); }
}
@media (max-width: 768px) {
  .layout-main { padding: var(--space-4); }
  .layout-footer { padding: var(--space-3) var(--space-4); }
}
</style>

