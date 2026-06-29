<script setup lang="ts">
// StarMap root component
</script>

<template>
  <router-view v-slot="{ Component, route }">
    <transition
      :name="(route.meta?.transition as string) || 'page-fade'"
      mode="out-in"
    >
      <component :is="Component" :key="route.path" />
    </transition>
  </router-view>
</template>

<style>
:root {
  --radius: 0.625rem;
  --radius-sm: calc(var(--radius) * 0.6);
  --radius-md: calc(var(--radius) * 0.8);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4);
  --radius-full: 9999px;
  --background: #f8fafc;
  --foreground: #0f172a;
  --card: #ffffff;
  --card-foreground: #0f172a;
  --primary: #4f46e5;
  --primary-foreground: #ffffff;
  --primary-hover: #4338ca;
  --primary-ghost: rgba(79, 70, 229, 0.08);
  --secondary: #f1f5f9;
  --secondary-foreground: #1e293b;
  --muted: #f1f5f9;
  --muted-foreground: #64748b;
  --accent: #f1f5f9;
  --accent-foreground: #1e293b;
  --success: #10b981;
  --success-ghost: rgba(16, 185, 129, 0.10);
  --warning: #f59e0b;
  --warning-ghost: rgba(245, 158, 11, 0.10);
  --destructive: #ef4444;
  --destructive-ghost: rgba(239, 68, 68, 0.10);
  --info: #3b82f6;
  --info-ghost: rgba(59, 130, 246, 0.10);
  --border: #e2e8f0;
  --input: #e2e8f0;
  --ring: #4f46e5;
  --chart-1: #6366f1;
  --chart-2: #06b6d4;
  --chart-3: #8b5cf6;
  --chart-4: #f59e0b;
  --chart-5: #10b981;
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  --font-size-xs: 0.75rem;
  --font-size-sm: 0.8125rem;
  --font-size-base: 0.875rem;
  --font-size-lg: 1rem;
  --font-size-xl: 1.125rem;
  --font-size-2xl: 1.25rem;
  --font-size-3xl: 1.5rem;
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-10: 2.5rem;
  --space-12: 3rem;
  --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.04);
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-fast: 150ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;
  --z-dropdown: 1000;
  --z-sticky: 1020;
  --z-modal: 1050;
}
html.dark {
  --background: #0c0f1a;
  --foreground: #e2e8f0;
  --card: #141827;
  --card-foreground: #e2e8f0;
  --primary: #818cf8;
  --primary-foreground: #0f0f23;
  --primary-hover: #a5b4fc;
  --primary-ghost: rgba(129, 140, 248, 0.12);
  --secondary: #1e293b;
  --secondary-foreground: #e2e8f0;
  --muted: #1e293b;
  --muted-foreground: #94a3b8;
  --accent: #1e293b;
  --success: #34d399;
  --success-ghost: rgba(52, 211, 153, 0.12);
  --warning: #fbbf24;
  --warning-ghost: rgba(251, 191, 36, 0.12);
  --destructive: #f87171;
  --destructive-ghost: rgba(248, 113, 113, 0.12);
  --info: #60a5fa;
  --info-ghost: rgba(96, 165, 250, 0.12);
  --border: #1e293b;
  --input: #1e293b;
  --ring: #818cf8;
  --chart-1: #818cf8;
  --chart-2: #22d3ee;
  --chart-3: #a78bfa;
  --chart-4: #fbbf24;
  --chart-5: #34d399;
}
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
html { font-size: 16px; -webkit-font-smoothing: antialiased; }
body { font-family: var(--font-sans); font-size: var(--font-size-base); color: var(--foreground); background: var(--background); line-height: 1.6; letter-spacing: -0.01em; }
.page-fade-enter-active, .page-fade-leave-active { transition: opacity var(--duration-slow) var(--ease-out); }
.page-fade-enter-from, .page-fade-leave-to { opacity: 0; }
a { color: var(--primary); text-decoration: none; transition: color var(--duration-fast); }
a:hover { color: var(--primary-hover); }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
.el-card { border-radius: var(--radius-xl) !important; border: 1px solid var(--border) !important; background: var(--card) !important; color: var(--card-foreground) !important; box-shadow: var(--shadow-xs) !important; transition: box-shadow var(--duration-normal) var(--ease-out), border-color var(--duration-normal) var(--ease-out); }
.el-card:hover { box-shadow: var(--shadow-sm) !important; }
.el-card[shadow="hover"]:hover { box-shadow: var(--shadow-md) !important; border-color: color-mix(in srgb, var(--primary) 15%, var(--border)) !important; }
.el-card__header { padding: var(--space-4) var(--space-5) !important; border-bottom: 1px solid var(--border) !important; font-weight: 600; font-size: var(--font-size-base); color: var(--card-foreground); letter-spacing: -0.01em; background: var(--card) !important; }
.el-card__body { padding: var(--space-5) !important; }
.el-button { border-radius: var(--radius-lg) !important; font-weight: 500; letter-spacing: -0.01em;  } el-button:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }
.el-button--primary { --el-button-bg-color: var(--primary); --el-button-border-color: var(--primary); --el-button-hover-bg-color: var(--primary-hover); --el-button-hover-border-color: var(--primary-hover); --el-button-text-color: var(--primary-foreground); }
.el-button--default { --el-button-bg-color: var(--card); --el-button-border-color: var(--border); --el-button-hover-bg-color: var(--accent); --el-button-hover-border-color: var(--primary); --el-button-text-color: var(--foreground); }
.el-input__wrapper { border-radius: var(--radius-md) !important; box-shadow: 0 0 0 1px var(--input) !important; background: var(--card) !important; transition: box-shadow var(--duration-fast); }
.el-input__wrapper:hover { box-shadow: 0 0 0 1px var(--muted-foreground) !important; }
.el-input__wrapper.is-focus { box-shadow: 0 0 0 2px color-mix(in srgb, var(--ring) 25%, transparent) !important; }
.el-textarea__inner { border-radius: var(--radius-md) !important; border-color: var(--input) !important; background: var(--card) !important; color: var(--foreground) !important; }
.el-tag { border-radius: var(--radius-sm) !important; font-weight: 500; }
.el-table th.el-table__cell { background: var(--muted) !important; color: var(--muted-foreground) !important; font-weight: 600; font-size: var(--font-size-sm); text-transform: uppercase; letter-spacing: 0.04em; }
.el-table { --el-table-border-color: var(--border); --el-table-tr-bg-color: var(--card); --el-table-row-hover-bg-color: var(--accent); } .el-table tr { transition: background var(--duration-fast); }
.el-descriptions { --el-descriptions-item-bordered-label-background: var(--muted); }
.el-drawer { background: var(--card) !important; }
.el-breadcrumb__inner { color: var(--muted-foreground) !important; font-size: var(--font-size-sm); }
.el-menu--horizontal { border-bottom: none !important; }
.glass { background: color-mix(in srgb, var(--card) 80%, transparent); backdrop-filter: blur(12px) saturate(1.5); -webkit-backdrop-filter: blur(12px) saturate(1.5); }
@keyframes fade-in-up { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.animate-fade-in { animation: fade-in-up 0.4s var(--ease-out) both; }
@media (max-width: 768px) { html { font-size: 14px; } .el-card__body { padding: var(--space-4) !important; } .el-card__header { padding: var(--space-3) var(--space-4) !important; } }

/* ── Enhanced Element Plus Overrides ── */
.el-button--primary:active { transform: scale(0.98); }
.el-button--default:active { transform: scale(0.98); }
.el-radio-button__inner { border-radius: var(--radius-md) !important; font-weight: 500; }
.el-radio-button__original-radio:checked+.el-radio-button__inner {
  background-color: var(--primary) !important;
  border-color: var(--primary) !important;
  color: var(--primary-foreground) !important;
  box-shadow: var(--shadow-sm) !important;
}
.el-step__head.is-finish { color: var(--primary) !important; border-color: var(--primary) !important; }
.el-step__title.is-finish { color: var(--primary) !important; }
.el-step__head.is-process { color: var(--primary) !important; border-color: var(--primary) !important; }
.el-step__title.is-process { color: var(--foreground) !important; font-weight: 600; }
.el-tag--success { --el-tag-bg-color: var(--success-ghost); --el-tag-text-color: var(--success); --el-tag-border-color: transparent; }
.el-tag--warning { --el-tag-bg-color: var(--warning-ghost); --el-tag-text-color: var(--warning); --el-tag-border-color: transparent; }
.el-tag--danger { --el-tag-bg-color: var(--destructive-ghost); --el-tag-text-color: var(--destructive); --el-tag-border-color: transparent; }
.el-tag--info { --el-tag-bg-color: var(--info-ghost); --el-tag-text-color: var(--info); --el-tag-border-color: transparent; }
.el-tag--primary { --el-tag-bg-color: var(--primary-ghost); --el-tag-text-color: var(--primary); --el-tag-border-color: transparent; }
.el-loading-mask { background: color-mix(in srgb, var(--background) 80%, transparent) !important; }
.el-message-box { border-radius: var(--radius-xl) !important; border: 1px solid var(--border) !important; }
.el-notification { border-radius: var(--radius-xl) !important; border: 1px solid var(--border) !important; }
.el-tooltip__popper { border-radius: var(--radius-md) !important; font-size: var(--font-size-xs) !important; }

/* ── Focus Ring Utility ── */
.focus-ring:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; border-radius: var(--radius-sm); }

/* ── Subtle Hover Lift ── */
.hover-lift { transition: transform var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out); }
.hover-lift:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }

/* ── Smooth background transition for dark mode ── */
html { transition: background-color var(--duration-slow) var(--ease-in-out), color var(--duration-slow) var(--ease-in-out); }
.el-card, .el-button, .el-input__wrapper, .el-textarea__inner { transition: background-color var(--duration-normal) var(--ease-in-out), border-color var(--duration-normal) var(--ease-in-out), box-shadow var(--duration-normal) var(--ease-in-out); }

/* ── Selection Color ── */
::selection { background: color-mix(in srgb, var(--primary) 20%, transparent); color: var(--foreground); }

/* ── Print Styles ── */
@media print { .nav-bar, .breadcrumb-bar, .layout-footer, .mobile-menu { display: none !important; } .layout-main { padding: 0 !important; max-width: 100% !important; } }
</style>