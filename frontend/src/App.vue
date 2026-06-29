<script setup lang="ts">
// StarMap root component
</script>

<template>
  <router-view v-slot="{ Component, route }">
    <transition
      :name="(route.meta?.transition as string) || 'page-fade'"
      mode="out-in"
    >
      <component
        :is="Component"
        :key="route.path"
      />
    </transition>
  </router-view>
</template>

<style>
:root {
  /* ── Radius ── */
  --radius: 0.625rem;
  --radius-xs: calc(var(--radius) * 0.4);
  --radius-sm: calc(var(--radius) * 0.6);
  --radius-md: calc(var(--radius) * 0.8);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4);
  --radius-2xl: calc(var(--radius) * 2);
  --radius-full: 9999px;

  /* ── Surfaces ── */
  --background: #fafbfc;
  --foreground: #0a0a0b;
  --card: #ffffff;
  --card-foreground: #0a0a0b;
  --popover: #ffffff;
  --popover-foreground: #0a0a0b;
  --primary: #4f46e5;
  --primary-foreground: #ffffff;
  --primary-hover: #4338ca;
  --primary-ghost: rgba(79, 70, 229, 0.06);
  --primary-subtle: rgba(79, 70, 229, 0.03);
  --secondary: #f4f5f7;
  --secondary-foreground: #1a1d23;
  --muted: #f4f5f7;
  --muted-foreground: #6b7280;
  --accent: #f4f5f7;
  --accent-foreground: #1a1d23;
  --success: #059669;
  --success-ghost: rgba(5, 150, 105, 0.06);
  --warning: #d97706;
  --warning-ghost: rgba(217, 119, 6, 0.06);
  --destructive: #dc2626;
  --destructive-ghost: rgba(220, 38, 38, 0.06);
  --info: #2563eb;
  --info-ghost: rgba(37, 99, 235, 0.06);
  --border: #e5e7eb;
  --input: #e5e7eb;
  --ring: #4f46e5;

  /* ── Chart Palette ── */
  --chart-1: #6366f1;
  --chart-2: #0891b2;
  --chart-3: #8b5cf6;
  --chart-4: #d97706;
  --chart-5: #059669;

  /* ── Typography ── */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
  --font-size-xs: 0.6875rem;
  --font-size-sm: 0.8125rem;
  --font-size-base: 0.875rem;
  --font-size-lg: 1rem;
  --font-size-xl: 1.125rem;
  --font-size-2xl: 1.25rem;
  --font-size-3xl: 1.5rem;
  --font-size-4xl: 2rem;
  --leading-tight: 1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.625;
  --tracking-tight: -0.025em;
  --tracking-normal: -0.01em;
  --tracking-wide: 0.025em;

  /* ── Spacing ── */
  --space-0: 0;
  --space-0-5: 0.125rem;
  --space-1: 0.25rem;
  --space-1-5: 0.375rem;
  --space-2: 0.5rem;
  --space-2-5: 0.625rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-10: 2.5rem;
  --space-12: 3rem;
  --space-16: 4rem;

  /* ── Shadows ── */
  --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.03);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.03);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.03);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.06), 0 4px 6px -4px rgba(0, 0, 0, 0.03);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.06), 0 8px 10px -6px rgba(0, 0, 0, 0.03);
  --shadow-glow: 0 0 0 3px rgba(79, 70, 229, 0.12);
  --shadow-glow-success: 0 0 0 3px rgba(5, 150, 105, 0.12);
  --shadow-glow-destructive: 0 0 0 3px rgba(220, 38, 38, 0.12);

  /* ── Motion ── */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --duration-fast: 150ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;
  --duration-slower: 500ms;

  /* ── Z-Index ── */
  --z-base: 0;
  --z-dropdown: 1000;
  --z-sticky: 1020;
  --z-overlay: 1040;
  --z-modal: 1050;
  --z-popover: 1060;
  --z-tooltip: 1070;

  /* ── Layout ── */
  --sidebar-width: 260px;
  --sidebar-width-collapsed: 64px;
  --header-height: 56px;
  --content-max-width: 1400px;
}
html.dark {
  --background: #09090b;
  --foreground: #fafafa;
  --card: #111113;
  --card-foreground: #fafafa;
  --popover: #111113;
  --popover-foreground: #fafafa;
  --primary: #818cf8;
  --primary-foreground: #09090b;
  --primary-hover: #a5b4fc;
  --primary-ghost: rgba(129, 140, 248, 0.10);
  --primary-subtle: rgba(129, 140, 248, 0.05);
  --secondary: #1c1c1f;
  --secondary-foreground: #e4e4e7;
  --muted: #1c1c1f;
  --muted-foreground: #a1a1aa;
  --accent: #1c1c1f;
  --accent-foreground: #e4e4e7;
  --success: #34d399;
  --success-ghost: rgba(52, 211, 153, 0.10);
  --warning: #fbbf24;
  --warning-ghost: rgba(251, 191, 36, 0.10);
  --destructive: #f87171;
  --destructive-ghost: rgba(248, 113, 113, 0.10);
  --info: #60a5fa;
  --info-ghost: rgba(96, 165, 250, 0.10);
  --border: #27272a;
  --input: #27272a;
  --ring: #818cf8;
  --chart-1: #818cf8;
  --chart-2: #22d3ee;
  --chart-3: #a78bfa;
  --chart-4: #fbbf24;
  --chart-5: #34d399;
  --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.15);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.2), 0 1px 2px rgba(0, 0, 0, 0.15);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.25), 0 2px 4px -2px rgba(0, 0, 0, 0.15);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -4px rgba(0, 0, 0, 0.15);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.35), 0 8px 10px -6px rgba(0, 0, 0, 0.15);
  --shadow-glow: 0 0 0 3px rgba(129, 140, 248, 0.15);
  --shadow-glow-success: 0 0 0 3px rgba(52, 211, 153, 0.15);
  --shadow-glow-destructive: 0 0 0 3px rgba(248, 113, 113, 0.15);
}
tml.dark {
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
.page-slide-enter-active, .page-slide-leave-active {
  transition: opacity var(--duration-slow) var(--ease-out), transform var(--duration-slow) var(--ease-out);
}
.page-slide-enter-from { opacity: 0; transform: translateY(12px); }
.page-slide-leave-to { opacity: 0; transform: translateY(-8px); }
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

/* ── Skeleton Loading ── */
@keyframes skeleton-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}
.skeleton {
  background: linear-gradient(90deg, var(--muted) 25%, var(--accent) 50%, var(--muted) 75%);
  background-size: 200% 100%;
  animation: skeleton-pulse 1.8s ease-in-out infinite;
  border-radius: var(--radius-md);
}

/* ── Subtle Noise Grain (anti-AI feel) ── */
.grain { position: relative; }
.grain::before {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.02;
  pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  z-index: 1;
  border-radius: inherit;
}

/* ── Content Width ── */
.content-narrow { max-width: 720px; margin: 0 auto; }
.content-medium { max-width: 960px; margin: 0 auto; }
.content-wide { max-width: 1200px; margin: 0 auto; }

/* ── Divider ── */
.divider {
  height: 1px;
  background: var(--border);
  border: none;
  margin: var(--space-4) 0;
}

/* ── Badge ── */
.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px var(--space-2);
  font-size: var(--font-size-xs);
  font-weight: 500;
  border-radius: var(--radius-full);
  line-height: 1.4;
}

/* ── Tab Underline ── */
.tab-underline {
  position: relative;
}
.tab-underline::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--primary);
  border-radius: 1px;
  transform: scaleX(0);
  transition: transform var(--duration-normal) var(--ease-out);
}
.tab-underline.active::after {
  transform: scaleX(1);
}

/* ── Section Header ── */
.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: var(--space-5);
}
.section-title {
  font-size: var(--font-size-2xl);
  font-weight: 800;
  color: var(--foreground);
  letter-spacing: var(--tracking-tight);
  line-height: var(--leading-tight);
}
.section-subtitle {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin-top: var(--space-1);
}

/* ── Stagger Animation ── */
@keyframes stagger-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
.stagger > * {
  animation: stagger-in 0.35s var(--ease-out) both;
}
.stagger > *:nth-child(1) { animation-delay: 0ms; }
.stagger > *:nth-child(2) { animation-delay: 50ms; }
.stagger > *:nth-child(3) { animation-delay: 100ms; }
.stagger > *:nth-child(4) { animation-delay: 150ms; }
.stagger > *:nth-child(5) { animation-delay: 200ms; }
.stagger > *:nth-child(6) { animation-delay: 250ms; }

/* ── Interactive Card ── */
.card-interactive {
  transition: all var(--duration-normal) var(--ease-out);
  cursor: pointer;
}
.card-interactive:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: color-mix(in srgb, var(--primary) 15%, var(--border));
}
.card-interactive:active {
  transform: translateY(0);
  box-shadow: var(--shadow-xs);
}

/* ── Subtle Border Glow on Hover ── */
.border-glow {
  transition: box-shadow var(--duration-normal) var(--ease-out);
}
.border-glow:hover {
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--primary) 20%, transparent), var(--shadow-sm);
}

</style>