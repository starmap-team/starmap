<script setup lang="ts">
/**
 * PageHeaderIcon — Page title icon (Linear/Vercel/Stripe Docs/GitHub Primer 2024)
 *
 * Design language (matches BusinessBanner):
 *  - Rounded square badge tinted with a type-specific accent color
 *  - Element Plus icon centered inside (NOT emoji)
 *  - Sits inline before the page <h1>/<h2> title
 *  - Accessible: aria-hidden, decorative; screen readers see the heading text
 *
 * Usage:
 *   <h2 class="starmap-page-title">
 *     <PageHeaderIcon kind="loop" />
 *     闭环验证演示
 *   </h2>
 *
 * Add new kinds here as pages are added. Each kind maps a semantic name to:
 *  - icon: Element Plus icon component (required — no emoji)
 *  - accent: CSS variable for the badge tint (defaults to --info)
 */
import {
  Refresh,
  DataBoard,
  Setting,
  DocumentChecked,
  Reading,
  UserFilled,
  Aim,
  DataAnalysis,
  Position,
  List,
  Connection,
  Cpu,
  Histogram,
  TrendCharts,
  EditPen,
  Document,
  User,
  Files,
  Histogram as DataHistogram,
  RefreshRight,
} from '@element-plus/icons-vue'
import type { Component } from 'vue'
import { computed } from 'vue'

export type PageIconKind =
  | 'loop'
  | 'dashboard'
  | 'admin'
  | 'extract'
  | 'learning'
  | 'login'
  | 'match'
  | 'analysis'
  | 'position-detail'
  | 'position-list'
  | 'datasources'
  | 'pipeline'
  | 'quality'
  | 'evolution'
  | 'password'
  | 'audit'
  | 'users'
  | 'resume'
  | 'sync'

interface KindConfig {
  icon: Component
  /** Accent color CSS variable name (without `var(...)`). */
  accent: string
}

const KIND_MAP: Record<PageIconKind, KindConfig> = {
  loop:            { icon: Refresh,        accent: '--info' },
  dashboard:       { icon: DataBoard,      accent: '--info' },
  admin:           { icon: Setting,        accent: '--muted-foreground' },
  extract:         { icon: DocumentChecked,accent: '--success' },
  learning:        { icon: Reading,        accent: '--info' },
  login:           { icon: UserFilled,     accent: '--info' },
  match:           { icon: Aim,            accent: '--success' },
  analysis:        { icon: DataAnalysis,   accent: '--info' },
  'position-detail': { icon: Position,     accent: '--info' },
  'position-list': { icon: List,           accent: '--info' },
  datasources:     { icon: Connection,     accent: '--info' },
  pipeline:        { icon: Cpu,            accent: '--warning' },
  quality:         { icon: Histogram,      accent: '--success' },
  evolution:       { icon: TrendCharts,    accent: '--info' },
  password:        { icon: EditPen,        accent: '--warning' },
  audit:           { icon: Document,       accent: '--muted-foreground' },
  users:           { icon: User,           accent: '--info' },
  resume:          { icon: Files,          accent: '--info' },
  sync:            { icon: RefreshRight,   accent: '--info' },
}

const props = withDefaults(defineProps<{
  kind: PageIconKind
  /** Override the accent color CSS variable (e.g. "--warning"). */
  accent?: string
  /** Icon pixel size. Default 20 (matches BusinessBanner 32px badge). */
  size?: number
}>(), {
  accent: '',
  size: 20,
})

const resolved = computed(() => KIND_MAP[props.kind])
const accentVar = computed(() => props.accent || resolved.value.accent)
</script>

<template>
  <span
    class="page-header-icon"
    :style="{ '--phi-accent': `var(${accentVar})` }"
    aria-hidden="true"
  >
    <el-icon :size="size">
      <component :is="resolved.icon" />
    </el-icon>
  </span>
</template>

<style scoped>
.page-header-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--phi-accent) 12%, transparent);
  color: var(--phi-accent);
  flex-shrink: 0;
  transition: background-color var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
}
.page-header-icon:hover {
  background: color-mix(in srgb, var(--phi-accent) 18%, transparent);
}
</style>