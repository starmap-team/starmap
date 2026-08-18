<script setup lang="ts">
/**
 * BusinessBanner — 业务说明横幅
 *
 * 设计目标（参考 Linear / Vercel Docs / Stripe Docs / GitHub Primer 2024 模式）：
 * 1. 视觉层级清晰：4px 左侧强调色边 + 类型图标 + 章节徽章 + 类型标签
 * + 标题 + 描述 + 结构化元数据芯片（替代旧的纯文本 + <code> 行）
 * 2. 信息密度可控：紧凑模式 + 可选折叠，避免长描述压垮首屏
 * 3. 键盘可达 + ARIA：role=note/alert、键盘聚焦、所有交互元素焦点环
 * 4. 暗色模式原生支持：复用 App.vue 既有 --success/-warning/-info/-destructive/-ghost token
 * 5. 零 v-html：meta 数组化 + 自动从旧字符串解析 <code> 片段，零 XSS 风险
 *
 * Usage (推荐):
 * <BusinessBanner
 * type="info"
 * title="L2 数据融合层 — ETL 流水线监控"
 * description="全链路 ETL DAG：爬虫采集 → (去重 ∥ 清洗) → LLM 抽取 → 入库 → 图谱构建"
 * :meta="[
 * { category: '后端', label: '/pipeline/*', code: true, copyable: true },
 * { category: '数据源', label: 'pipeline_runs', code: true, copyable: true },
 * { label: 'Neo4j' },
 * { label: 'SSE 实时推送', copyable: false },
 * ]"
 * collapsible
 * />
 *
 * Usage (向后兼容 — 旧 meta 字符串 + <code>):
 * <BusinessBanner
 * type="success"
 * title="L2 数据融合层 — ETL 流水线监控"
 * description="全链路 ETL DAG..."
 * meta="后端: <code>/pipeline/*</code> · 数据源: <code>pipeline_runs</code> + Neo4j · SSE 实时推送"
 * />
 */
import { computed, ref } from 'vue'
import {
  CircleCheckFilled,
  CircleCloseFilled,
  InfoFilled,
  WarningFilled,
  Document,
  CopyDocument,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

export type BannerType = 'info' | 'success' | 'warning' | 'error' | 'note'

export interface BannerMetaItem {
 /** Displayed text. When `code` is true, rendered in monospace. */
  label: string
 /** Render label in monospace chip (legacy <code> behavior). */
  code?: boolean
 /** Optional category label rendered as a muted prefix (e.g. "后端:"). */
  category?: string
 /** Show copy-to-clipboard icon on hover. Defaults to true when code=true. */
  copyable?: boolean
 /** Optional tooltip text shown on hover. */
  hint?: string
}

const props = withDefaults(defineProps<{
 /** Element Plus alert-style type, extended with 'note' for neutral callouts. */
  type?: BannerType
 /** Plain-text title (NOT v-html — XSS-safe). */
  title: string
 /** Plain-text description (NOT v-html). */
  description?: string
 /** Section reference, e.g. "". Rendered as a monospace pill. */
  section?: string
 /**
 * Structured meta tags (preferred) OR legacy HTML string with `<code>...</code>`
 * segments separated by ` · `. Strings are auto-parsed for back-compat.
 */
  meta?: BannerMetaItem[] | string
 /** Allow collapsing long descriptions. Default: false. */
  collapsible?: boolean
 /** Initial collapsed state when collapsible=true. Default: false. */
  defaultCollapsed?: boolean
 /** Reduce padding for use in dense layouts. Default: false. */
  compact?: boolean
 /** Override default aria-label. */
  ariaLabel?: string
}>(), {
  type: 'info',
  description: '',
  section: '',
  meta: () => [],
  collapsible: false,
  defaultCollapsed: false,
  compact: false,
  ariaLabel: '',
})

const collapsed = ref(props.defaultCollapsed)

/* ─── Per-type design tokens (mapped to existing App.vue CSS variables) ── */

interface TypeTokens {
 /** Top/left accent color (used for border, icon color, label chip). */
  accent: string
 /** Tinted background color (uses 6-10% opacity ghost tokens). */
  bg: string
 /** Type label text (uppercase chip). */
  label: string
 /** Element Plus icon component. */
  icon: typeof CircleCheckFilled
 /** ARIA role for the banner. */
  role: 'note' | 'alert'
}

const TOKENS: Record<BannerType, TypeTokens> = {
  info: {
    accent: 'var(--info)',
    bg: 'var(--info-ghost)',
    label: 'INFO',
    icon: InfoFilled,
    role: 'note',
  },
  success: {
    accent: 'var(--success)',
    bg: 'var(--success-ghost)',
    label: 'SUCCESS',
    icon: CircleCheckFilled,
    role: 'note',
  },
  warning: {
    accent: 'var(--warning)',
    bg: 'var(--warning-ghost)',
    label: 'WARNING',
    icon: WarningFilled,
    role: 'note',
  },
  error: {
    accent: 'var(--destructive)',
    bg: 'var(--destructive-ghost)',
    label: 'ERROR',
    icon: CircleCloseFilled,
    role: 'alert',
  },
  note: {
    accent: 'var(--muted-foreground)',
    bg: 'var(--muted)',
    label: 'NOTE',
    icon: Document,
    role: 'note',
  },
}

const tokens = computed(() => TOKENS[props.type])

/* ─── Meta: structured array OR legacy string parser ── */

const parsedMeta = computed<BannerMetaItem[]>(() => {
  if (Array.isArray(props.meta)) return props.meta
  if (typeof props.meta !== 'string' || !props.meta.trim()) return []

 // Legacy strings look like: 后端: <code>/pipeline/*</code> · 数据源: <code>pipeline_runs</code> + Neo4j
 // Strategy: split by ` · `, then for each segment extract leading "Category:" + <code>...</code> tokens.
  const segments = props.meta.split(/\s*·\s*/)
  const items: BannerMetaItem[] = []
  for (const segment of segments) {
 // Pull out all <code>...</code> spans (in case of multiple per segment)
    const codeRegex = /<code>([^<]+)<\/code>/g
    const codeLabels: string[] = []
    let match: RegExpExecArray | null
    let lastIndex = 0
    let prefixText = ''
    while ((match = codeRegex.exec(segment)) !== null) {
      prefixText += segment.slice(lastIndex, match.index)
      codeLabels.push(match[1])
      lastIndex = codeRegex.lastIndex
    }
    prefixText += segment.slice(lastIndex)

 // If there are code tokens, emit one item per code; otherwise emit the plain text.
    if (codeLabels.length > 0) {
 // Pull out a leading "Category:" (e.g. "后端:") from the prefix before the first code
      const catMatch = prefixText.match(/^([\u4e00-\u9fa5A-Za-z]+)\s*[:：]\s*/)
      const category = catMatch ? catMatch[1] : undefined
      for (const label of codeLabels) {
        items.push({ label, code: true, copyable: true, category })
      }
 // Trailing text after the last code (e.g. "+ Neo4j")
      const trailing = prefixText.replace(/^([\u4e00-\u9fa5A-Za-z]+)\s*[:：]\s*/, '').trim()
      if (trailing) {
        items.push({ label: trailing.startsWith('+') ? trailing.slice(1).trim() : trailing, code: false })
      }
    } else {
      const trimmed = prefixText.trim()
      if (trimmed) items.push({ label: trimmed, code: false })
    }
  }
  return items
})

/* ─── Interactions ── */

async function copyValue(item: BannerMetaItem) {
  const isCopyable = item.copyable ?? item.code
  if (!isCopyable) return
  try {
    await navigator.clipboard.writeText(item.label)
    ElMessage.success(`已复制: ${item.label}`)
  } catch {
 // Clipboard API blocked (e.g. insecure context) — fall back to selection
    const ta = document.createElement('textarea')
    ta.value = item.label
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch { /* swallow */ }
    document.body.removeChild(ta)
    ElMessage.success(`已复制: ${item.label}`)
  }
}

function toggleCollapsed() {
  if (props.collapsible) collapsed.value = !collapsed.value
}

const showCollapseToggle = computed(
  () => props.collapsible && (props.description?.length ?? 0) > 60,
)

const computedAriaLabel = computed(() => {
  if (props.ariaLabel) return props.ariaLabel
  const section = props.section ? `${props.section} ` : ''
  return `${section}${props.title}`
})
</script>

<template>
  <div
    class="biz-banner"
    :class="[
      `biz-banner--${type}`,
      { 'biz-banner--compact': compact, 'biz-banner--collapsed': collapsed && showCollapseToggle },
    ]"
    :role="tokens.role"
    :aria-label="computedAriaLabel"
    :style="{
      '--banner-accent': tokens.accent,
      '--banner-bg': tokens.bg,
    }"
  >
    <span
      class="biz-banner__accent"
      aria-hidden="true"
    />

    <div class="biz-banner__icon">
      <el-icon :size="18">
        <component :is="tokens.icon" />
      </el-icon>
    </div>

    <div class="biz-banner__body">
      <header class="biz-banner__head">
        <span
          v-if="section"
          class="biz-banner__section"
          aria-label="章节"
        >{{ section }}</span>
        <span class="biz-banner__type">{{ tokens.label }}</span>
        <h3 class="biz-banner__title">
          {{ title }}
        </h3>
        <button
          v-if="showCollapseToggle"
          type="button"
          class="biz-banner__toggle"
          :aria-expanded="!collapsed"
          :aria-label="collapsed ? '展开详情' : '收起详情'"
          @click="toggleCollapsed"
        >
          {{ collapsed ? '展开' : '收起' }}
        </button>
      </header>

      <p
        v-if="description && !collapsed"
        class="biz-banner__desc"
      >
        {{ description }}
      </p>

      <ul
        v-if="parsedMeta.length && !collapsed"
        class="biz-banner__meta"
        aria-label="元数据"
      >
        <li
          v-for="(item, i) in parsedMeta"
          :key="`${item.label}-${i}`"
          class="biz-banner__meta-item"
        >
          <span
            v-if="item.category"
            class="biz-banner__meta-cat"
          >{{ item.category }}:</span>
          <span
            class="biz-banner__meta-chip"
            :class="{
              'is-code': item.code,
              'is-copyable': (item.copyable ?? item.code),
            }"
            :title="item.hint"
            :tabindex="(item.copyable ?? item.code) ? 0 : -1"
            :role="(item.copyable ?? item.code) ? 'button' : undefined"
            @click="copyValue(item)"
            @keydown.enter.prevent="copyValue(item)"
            @keydown.space.prevent="copyValue(item)"
          >
            <span class="biz-banner__meta-label">{{ item.label }}</span>
            <el-icon
              v-if="(item.copyable ?? item.code)"
              class="biz-banner__meta-copy"
              :size="12"
              aria-hidden="true"
            >
              <CopyDocument />
            </el-icon>
          </span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.biz-banner {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--banner-bg);
  border: 1px solid color-mix(in srgb, var(--banner-accent) 18%, var(--border));
  border-radius: var(--radius-lg);
  color: var(--foreground);
  margin-bottom: var(--space-4);
  transition: border-color var(--duration-normal) var(--ease-out),
              background-color var(--duration-normal) var(--ease-out);
}

.biz-banner--compact {
  padding: var(--space-2) var(--space-3);
  gap: var(--space-2);
}

/* Left accent stripe (the 4px colored bar — primary semantic signal) */
.biz-banner__accent {
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--banner-accent);
}

/* Icon — small rounded square in the type color */
.biz-banner__icon {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  margin-top: 2px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--banner-accent) 12%, transparent);
  color: var(--banner-accent);
}
.biz-banner--compact .biz-banner__icon {
  width: 26px;
  height: 26px;
  margin-top: 1px;
}

.biz-banner__body {
  flex: 1 1 auto;
  min-width: 0; /* allow content to shrink inside flex */
}

.biz-banner__head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: 2px;
}

/* chapter badge — monospace pill */
.biz-banner__section {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--banner-accent);
  background: color-mix(in srgb, var(--banner-accent) 10%, transparent);
  border-radius: var(--radius-sm);
}

/* Type label — uppercase chip (a11y: color is NOT the only signal) */
.biz-banner__type {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 var(--space-1-5);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--banner-accent);
  background: color-mix(in srgb, var(--banner-accent) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--banner-accent) 20%, transparent);
  border-radius: var(--radius-sm);
  text-transform: uppercase;
}

.biz-banner__title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  line-height: 1.4;
  letter-spacing: var(--tracking-normal);
  color: var(--foreground);
  flex: 1 1 auto;
  min-width: 0;
}
.biz-banner--compact .biz-banner__title {
  font-size: var(--font-size-sm);
}

.biz-banner__toggle {
  flex-shrink: 0;
  appearance: none;
  background: transparent;
  border: 1px solid color-mix(in srgb, var(--banner-accent) 25%, var(--border));
  border-radius: var(--radius-sm);
  padding: 0 var(--space-2);
  height: 22px;
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  cursor: pointer;
  transition: color var(--duration-fast), border-color var(--duration-fast);
}
.biz-banner__toggle:hover {
  color: var(--banner-accent);
  border-color: var(--banner-accent);
}
.biz-banner__toggle:focus-visible {
  outline: 2px solid var(--ring);
  outline-offset: 2px;
}

.biz-banner__desc {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-sm);
  line-height: var(--leading-relaxed);
  color: var(--muted-foreground);
}
.biz-banner--compact .biz-banner__desc {
  font-size: var(--font-size-xs);
  margin-top: 2px;
}

/* Meta chips row */
.biz-banner__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1-5);
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
}
.biz-banner--compact .biz-banner__meta {
  margin-top: var(--space-1);
  gap: var(--space-1);
}

.biz-banner__meta-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.biz-banner__meta-cat {
  font-size: var(--text-caption);
  color: var(--muted-foreground);
  font-weight: 500;
}

.biz-banner__meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px var(--space-2);
  font-size: var(--text-caption);
  line-height: 1.4;
  color: var(--foreground);
  background: color-mix(in srgb, var(--banner-accent) 6%, var(--card));
  border: 1px solid color-mix(in srgb, var(--banner-accent) 15%, var(--border));
  border-radius: var(--radius-sm);
  transition: background-color var(--duration-fast),
              border-color var(--duration-fast);
}
.biz-banner__meta-chip.is-code {
  font-family: var(--font-mono);
  font-size: 11px;
  background: color-mix(in srgb, var(--banner-accent) 8%, var(--muted));
}
.biz-banner__meta-chip.is-copyable {
  cursor: pointer;
}
.biz-banner__meta-chip.is-copyable:hover {
  background: color-mix(in srgb, var(--banner-accent) 18%, var(--card));
  border-color: color-mix(in srgb, var(--banner-accent) 45%, var(--border));
}
.biz-banner__meta-chip.is-copyable:focus-visible {
  outline: 2px solid var(--ring);
  outline-offset: 2px;
}
.biz-banner__meta-label { white-space: nowrap; }
.biz-banner__meta-copy {
  color: var(--muted-foreground);
  opacity: 0;
  transition: opacity var(--duration-fast);
}
.biz-banner__meta-chip.is-copyable:hover .biz-banner__meta-copy,
.biz-banner__meta-chip.is-copyable:focus-visible .biz-banner__meta-copy {
  opacity: 0.8;
}

/* Collapsed state — clamp description visibility */
.biz-banner--collapsed .biz-banner__head {
  margin-bottom: 0;
}

/* Dark theme tune-up: bump border contrast slightly */
html.dark .biz-banner {
  border-color: color-mix(in srgb, var(--banner-accent) 28%, var(--border));
}
html.dark .biz-banner__meta-chip {
  background: color-mix(in srgb, var(--banner-accent) 10%, var(--card));
}
html.dark .biz-banner__meta-chip.is-code {
  background: color-mix(in srgb, var(--banner-accent) 12%, var(--muted));
}

/* Responsive: stack meta chips under title on narrow screens */
@media (max-width: 640px) {
  .biz-banner__head {
    flex-wrap: wrap;
  }
  .biz-banner__title {
    width: 100%;
    order: 4;
  }
}
</style>
