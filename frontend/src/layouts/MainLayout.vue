<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { DataAnalysis, Connection, TrendCharts, Document, Setting, User, Sunny, MoonNight } from '@element-plus/icons-vue'
const route = useRoute()
const mobileMenuOpen = ref(false)
const isDark = ref(localStorage.getItem('theme') === 'dark')
if (isDark.value) document.documentElement.classList.add('dark')
function toggleDarkMode() { isDark.value = !isDark.value; document.documentElement.classList.toggle('dark', isDark.value); localStorage.setItem('theme', isDark.value ? 'dark' : 'light') }
const navItems = [
  { path: '/', title: '全景图谱', icon: Connection },
  { path: '/positions', title: '岗位列表', icon: User },
  { path: '/match', title: '匹配诊断', icon: DataAnalysis },
  { path: '/evolution', title: '演化看板', icon: TrendCharts },
  { path: '/extract', title: 'JD 抽取', icon: Document },
  { path: '/quality', title: '图谱质量', icon: DataAnalysis },
  { path: '/admin', title: '管理后台', icon: Setting },
]
const currentTitle = computed(() => navItems.find(i => i.path === route.path)?.title ?? '星图')
const breadcrumbs = computed(() => { const meta = route.meta as Record<string, any>; if (meta?.breadcrumb?.length) return meta.breadcrumb as string[]; return ['首页', currentTitle.value] })
function closeMobileMenu() { mobileMenuOpen.value = false }
</script>
<template>
  <div class="layout">
    <header class="nav-bar"><div class="nav-inner">
      <router-link to="/" class="nav-brand" @click="closeMobileMenu"><div class="brand-mark"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" fill="currentColor" opacity="0.9"/><circle cx="12" cy="12" r="7" stroke="currentColor" stroke-width="1.5" opacity="0.4"/><circle cx="12" cy="12" r="11" stroke="currentColor" stroke-width="1" opacity="0.15"/><circle cx="6" cy="8" r="1.5" fill="currentColor" opacity="0.6"/><circle cx="18" cy="6" r="1" fill="currentColor" opacity="0.4"/><circle cx="16" cy="18" r="1.2" fill="currentColor" opacity="0.5"/></svg></div><span class="brand-text">StarMap</span><span class="brand-badge">星图</span></router-link>
      <nav class="nav-links"><router-link v-for="item in navItems" :key="item.path" :to="item.path" class="nav-link" :class="{ active: route.path === item.path }" @click="closeMobileMenu">{{ item.title }}</router-link></nav>
      <div class="nav-actions"><button class="action-btn" @click="toggleDarkMode" :title="isDark ? '切换亮色' : '切换暗色'"><el-icon :size="16"><component :is="isDark ? Sunny : MoonNight" /></el-icon></button><button class="action-btn mobile-toggle" @click="mobileMenuOpen = !mobileMenuOpen"><span :class="{ open: mobileMenuOpen }"/><span :class="{ open: mobileMenuOpen }"/><span :class="{ open: mobileMenuOpen }"/></button></div>
    </div></header>
    <transition name="slide-down"><div v-if="mobileMenuOpen" class="mobile-menu glass"><router-link v-for="item in navItems" :key="item.path" :to="item.path" class="mobile-link" :class="{ active: route.path === item.path }" @click="closeMobileMenu"><el-icon :size="16"><component :is="item.icon" /></el-icon>{{ item.title }}</router-link></div></transition>
    <div class="breadcrumb-bar"><div class="breadcrumb-inner"><nav class="breadcrumbs"><template v-for="(crumb, idx) in breadcrumbs" :key="idx"><span v-if="idx > 0" class="bc-sep">/</span><span class="bc-item" :class="{ 'bc-current': idx === breadcrumbs.length - 1 }">{{ crumb }}</span></template></nav><span class="page-label">{{ currentTitle }}</span></div></div>
    <main class="layout-main"><slot /></main>
    <footer class="layout-footer"><div class="footer-inner"><span>StarMap &middot; 人才能力星云导航系统</span><span class="footer-sep">&middot;</span><span>{{ currentTitle }}</span></div></footer>
  </div>
</template>
<style scoped>
.layout { min-height: 100vh; display: flex; flex-direction: column; background: var(--background); }
.nav-bar { position: sticky; top: 0; z-index: var(--z-sticky); background: color-mix(in srgb, var(--card) 85%, transparent); backdrop-filter: blur(12px) saturate(1.8); -webkit-backdrop-filter: blur(12px) saturate(1.8); border-bottom: 1px solid var(--border); }
.nav-inner { display: flex; align-items: center; height: 56px; max-width: 1400px; margin: 0 auto; padding: 0 var(--space-6); gap: var(--space-8); }
.nav-brand { display: flex; align-items: center; gap: var(--space-3); text-decoration: none; flex-shrink: 0; }
.brand-mark { color: var(--primary); display: flex; align-items: center; }
.brand-text { font-size: var(--font-size-lg); font-weight: 700; color: var(--foreground); letter-spacing: -0.03em; }
.brand-badge { font-size: var(--font-size-xs); color: var(--muted-foreground); background: var(--secondary); padding: 1px 6px; border-radius: var(--radius-sm); font-weight: 500; }
.nav-links { display: flex; align-items: center; gap: var(--space-1); flex: 1; }
.nav-link { padding: var(--space-2) var(--space-3); font-size: var(--font-size-sm); font-weight: 500; color: var(--muted-foreground); text-decoration: none; border-radius: var(--radius-md); transition: all var(--duration-fast) var(--ease-in-out); white-space: nowrap; }
.nav-link:hover { color: var(--foreground); background: var(--accent); }
.nav-link.active { color: var(--primary); background: var(--primary-ghost); position: relative; }
.nav-link.active::after { content: ''; position: absolute; bottom: -1px; left: 50%; transform: translateX(-50%); width: 16px; height: 2px; background: var(--primary); border-radius: 1px; }
.nav-actions { display: flex; align-items: center; gap: var(--space-2); margin-left: auto; }
.action-btn { display: flex; align-items: center; justify-content: center; width: 34px; height: 34px; border: none; background: none; border-radius: var(--radius-md); color: var(--muted-foreground); cursor: pointer; transition: all var(--duration-fast); }
.action-btn:hover { color: var(--foreground); background: var(--accent); }
.mobile-toggle { display: none; flex-direction: column; gap: var(--space-1); padding: 6px; }
.mobile-toggle span { display: block; width: 18px; height: 2px; background: var(--foreground); border-radius: 1px; transition: all var(--duration-normal) var(--ease-out); }
.mobile-toggle span.open:nth-child(1) { transform: translateY(6px) rotate(45deg); }
.mobile-toggle span.open:nth-child(2) { opacity: 0; }
.mobile-toggle span.open:nth-child(3) { transform: translateY(-6px) rotate(-45deg); }
.mobile-menu { position: fixed; top: 56px; left: 0; right: 0; z-index: var(--z-dropdown); padding: var(--space-2) var(--space-4); border-bottom: 1px solid var(--border); }
.mobile-link { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-4); color: var(--foreground); text-decoration: none; border-radius: var(--radius-md); font-size: var(--font-size-base); font-weight: 500; transition: background var(--duration-fast); }
.mobile-link:hover, .mobile-link.active { background: var(--primary-ghost); color: var(--primary); }
.slide-down-enter-active, .slide-down-leave-active { transition: all var(--duration-normal) var(--ease-out); }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-8px); }
.breadcrumb-bar { background: var(--card); border-bottom: 1px solid var(--border); padding: var(--space-3) var(--space-6); }
.breadcrumb-inner { max-width: 1400px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; }
.breadcrumbs { display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-sm); }
.bc-sep { color: var(--border); }
.bc-item { color: var(--muted-foreground); }
.bc-current { color: var(--foreground); font-weight: 500; }
.page-label { font-size: var(--font-size-xs); color: var(--muted-foreground); }
.layout-main { flex: 1; max-width: 1400px; width: 100%; margin: 0 auto; padding: var(--space-6); }
.layout-footer { border-top: 1px solid var(--border); padding: var(--space-5) var(--space-6); background: var(--card); }
.footer-inner { max-width: 1400px; margin: 0 auto; display: flex; align-items: center; justify-content: center; gap: var(--space-2); font-size: var(--font-size-xs); color: var(--muted-foreground); }
.footer-sep { color: var(--border); }
@media (max-width: 768px) { .nav-inner { padding: 0 var(--space-4); } .nav-links { display: none; } .mobile-toggle { display: flex; } .brand-badge { display: none; } .breadcrumb-bar { padding: var(--space-2) var(--space-4); } .page-label { display: none; } .layout-main { padding: var(--space-4); } .layout-footer { padding: var(--space-3) var(--space-4); } }
</style>