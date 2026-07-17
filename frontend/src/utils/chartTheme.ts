/**
 * ECharts design-token bridge v3
 * Reads CSS custom properties at runtime so charts stay in sync with the theme.
 * Enhanced with Obsidian-inspired styling.
 */

/** Read a CSS custom property value from :root. Cached for performance. Shared across all chart/theme consumers. */
const _cvCache = new Map<string, string>()
let _cvObserver: MutationObserver | null = null

/** Lazily set up a MutationObserver that clears the cache when the theme class changes. */
function _ensureCacheInvalidation() {
  if (_cvObserver) return
  _cvObserver = new MutationObserver(() => {
    _cvCache.clear()
  })
  _cvObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['class'],
  })
  window.addEventListener('unload', () => {
    _cvObserver?.disconnect()
    _cvObserver = null
  })
}

export function cv(name: string): string {
  _ensureCacheInvalidation()
  let value = _cvCache.get(name)
  if (value === undefined) {
    value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
    _cvCache.set(name, value)
  }
  return value
}

/** Primary palette - maps to --chart-1..5 + semantic colors */
export function chartColors() {
  return {
    primary:   cv('--primary')   || '#4f46e5',
    success:   cv('--success')   || '#16a34a',
    warning:   cv('--warning')   || '#d97706',
    danger:    cv('--destructive') || '#dc2626',
    info:      cv('--info')      || '#2563eb',
    muted:     cv('--muted-foreground') || '#78716c',
    border:    cv('--border')    || '#e7e5e4',
    foreground: cv('--foreground') || '#1c1917',
    card:      cv('--card')      || '#ffffff',
    chart: [
      cv('--chart-1') || '#6366f1',
      cv('--chart-2') || '#0891b2',
      cv('--chart-3') || '#8b5cf6',
      cv('--chart-4') || '#d97706',
      cv('--chart-5') || '#16a34a',
    ],
  }
}

/** Shared ECharts tooltip config - clean, minimal */
export function tooltipStyle() {
  const c = chartColors()
  return {
    backgroundColor: c.card,
    borderColor: c.border,
    borderWidth: 1,
    textStyle: { color: c.foreground, fontSize: 12, fontFamily: `'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` },
    extraCssText: 'border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); padding: 8px 12px;',
  }
}

/** Shared splitLine style for axes */
export function splitLineStyle() {
  return { lineStyle: { type: 'dashed' as const, color: chartColors().border } }
}

/** Shared axis label style */
export function axisLabelStyle() {
  return { color: chartColors().muted, fontSize: 11 }
}

/** Shared ECharts legend text config */
export function legendStyle() {
  return { color: chartColors().muted, fontSize: 11, fontFamily: `'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` }
}

/** Gauge color thresholds - returns color based on value ranges */
export function gaugeColor(value: number, warn: number = 100, danger: number = 120) {
  const c = chartColors()
  if (value > danger) return c.danger
  if (value > warn) return c.warning
  return c.success
}

/** Axis style for consistent appearance */
export function axisStyle() {
  return {
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: splitLineStyle(),
    axisLabel: axisLabelStyle(),
  }
}

/** Shared G6 tooltip plugin style — mirrors ECharts tooltipStyle for G6's CSS-like property names */
export function g6TooltipStyle() {
  const c = chartColors()
  return {
    background: c.card,
    borderRadius: '10px',
    boxShadow: '0 6px 20px rgba(0,0,0,0.1)',
    padding: '8px 12px',
    fontSize: '12px',
    border: '1px solid ' + c.border,
    color: c.foreground,
  }
}

/** ECharts animation configuration for smooth transitions */
export function chartAnimationConfig() {
  return {
    animationDuration: 1000,
    animationEasing: 'cubicOut' as const,
    animationDelay: (idx: number) => idx * 50,
  }
}
