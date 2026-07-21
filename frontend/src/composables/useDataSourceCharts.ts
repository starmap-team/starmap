/**
 * DataSources chart options + format helpers — extracted from DataSources.vue (Phase 7 D)
 * Pure functions over chartColors() — no store dependency.
 */
import { chartColors, tooltipStyle, splitLineStyle, axisLabelStyle } from '@/utils/chartTheme'

export function getAuthorityGaugeOption(score: number): Record<string, unknown> {
  const colors = chartColors()
  const pct = Math.round(score * 100)
  let color = colors.danger
  if (pct >= 80) color = colors.success
  else if (pct >= 60) color = colors.warning

  return {
    series: [{
      type: 'gauge',
      startAngle: 220,
      endAngle: -40,
      radius: '90%',
      center: ['50%', '55%'],
      min: 0,
      max: 100,
      progress: { show: true, width: 10, roundCap: true, itemStyle: { color } },
      axisLine: { lineStyle: { width: 10, color: [[1, colors.border]] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      pointer: { show: false },
      detail: {
        valueAnimation: true,
        formatter: '{value}',
        fontSize: 20,
        fontWeight: 700,
        color: colors.foreground,
        offsetCenter: [0, '10%'],
      },
      title: { show: true, offsetCenter: [0, '40%'], fontSize: 10, color: colors.muted },
      data: [{ value: pct, name: '权威度' }],
    }],
  }
}

const WEEKDAY_LABELS = ['一', '二', '三', '四', '五', '六', '日'] as const

export function getDailyVolumeOption(volumes: number[]): Record<string, unknown> {
  const colors = chartColors()
  return {
    tooltip: { ...tooltipStyle(), trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { top: 8, bottom: 20, left: 28, right: 8 },
    xAxis: {
      type: 'category',
      data: volumes.map((_, i) => WEEKDAY_LABELS[i] ?? `D${i + 1}`),
      axisLabel: { ...axisLabelStyle(), fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      splitLine: splitLineStyle(),
      axisLabel: { ...axisLabelStyle(), fontSize: 9 },
    },
    series: [{
      type: 'bar',
      data: volumes.map((v, i) => ({
        value: v,
        itemStyle: {
          color: i === volumes.length - 1 ? colors.primary : colors.primary + '60',
          borderRadius: [3, 3, 0, 0],
        },
      })),
      barWidth: '55%',
    }],
  }
}

export interface StatusBadge {
  type: 'success' | 'warning' | 'danger' | 'info'
  label: string
}

export function getStatusBadge(status: string): StatusBadge {
  switch (status) {
    case 'active': return { type: 'success', label: '运行中' }
    case 'paused': return { type: 'warning', label: '已暂停' }
    case 'error':  return { type: 'danger',  label: '异常' }
    default:       return { type: 'info',    label: '未知' }
  }
}

const SOURCE_TYPE_LABELS: Record<string, string> = {
  crawler: '爬虫',
  api: 'API',
  manual: '手动',
  import: '导入',
  reference: '参考',
  internal: '内部',
}

export function getSourceTypeLabel(type: string): string {
  return SOURCE_TYPE_LABELS[type] ?? type
}

export function formatLastCrawl(dateStr: string): string {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  const diff = Date.now() - d.getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min}分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}小时前`
  const day = Math.floor(hr / 24)
  return `${day}天前`
}

export function formatRecords(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

/** 数据源名称中文化映射 — 覆盖爬虫平台、标准库、API 等常见数据源 */
const SOURCE_NAME_LABELS: Record<string, string> = {
  // 国内招聘平台
  boss: 'BOSS直聘',
  bosszhipin: 'BOSS直聘',
  'BOSS直聘': 'BOSS直聘',
  lagou: '拉勾网',
  '拉勾网': '拉勾网',
  '51job': '前程无忧',
  '51Job': '前程无忧',
  zhaopin: '智联招聘',
  liepin: '猎聘',
  talent: '猎聘',
  // 国际平台
  github: 'GitHub',
  GitHub: 'GitHub',
  indeed: 'Indeed',
  linkedin: 'LinkedIn',
  freelancer: 'Freelancer',
  // 标准库
  esco: 'ESCO 标准库',
  ESCO: 'ESCO 标准库',
  // 其他
  manual: '手动录入',
  import: '数据导入',
  api: 'API 接入',
  test_real_crawl: '测试数据',
  // 内部数据源标识
  jd_extract: 'JD 抽取',
  jd_extraction: 'JD 抽取',
  user_upload: '用户上传',
  // linkedin 已在上面定义
}

export function getSourceNameLabel(name: string): string {
  return SOURCE_NAME_LABELS[name] ?? name
}
