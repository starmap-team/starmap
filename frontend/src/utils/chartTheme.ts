/**
 * ECharts design-token bridge
 * Reads CSS custom properties at runtime so charts stay in sync with the theme.
 */

function cv(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/** Primary palette — maps to --chart-1..5 + semantic colors */
export function chartColors() {
  return {
    primary:   cv('--primary')   || '#4f46e5',
    success:   cv('--success')   || '#10b981',
    warning:   cv('--warning')   || '#f59e0b',
    danger:    cv('--destructive') || '#ef4444',
    info:      cv('--info')      || '#3b82f6',
    muted:     cv('--muted-foreground') || '#64748b',
    border:    cv('--border')    || '#e2e8f0',
    foreground: cv('--foreground') || '#0f172a',
    card:      cv('--card')      || '#ffffff',
    chart: [
      cv('--chart-1') || '#6366f1',
      cv('--chart-2') || '#06b6d4',
      cv('--chart-3') || '#8b5cf6',
      cv('--chart-4') || '#f59e0b',
      cv('--chart-5') || '#10b981',
    ],
  }
}

/** Shared ECharts tooltip config */
export function tooltipStyle() {
  const c = chartColors()
  return {
    backgroundColor: c.card,
    borderColor: c.border,
    borderWidth: 1,
    textStyle: { color: c.foreground, fontSize: 12, fontFamily: 'inherit' },
    extraCssText: 'border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);',
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

/** Gauge color thresholds — returns color based on value ranges */
export function gaugeColor(value: number, warn: number = 100, danger: number = 120) {
  const c = chartColors()
  if (value > danger) return c.danger
  if (value > warn) return c.warning
  return c.success
}