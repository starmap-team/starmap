/**
 * Format a date string as a relative time description (e.g., "3分钟前", "2小时前").
 */
export function formatRelativeTime(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diff = now - then
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}小时前`
  if (diff < 2_592_000_000) return `${Math.floor(diff / 86_400_000)}天前`
  return new Date(dateStr).toLocaleDateString()
}
