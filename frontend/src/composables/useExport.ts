/**
 * useExport — JSON/CSV 导出逻辑复用 composable
 *
 * 用法：
 * ```ts
 * const { exportJSON, exportCSV } = useExport()
 * exportJSON(data, 'report')
 * exportCSV(rows, 'report')
 * ```
 */

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function useExport() {
  function exportJSON(data: unknown, filename: string) {
    const json = JSON.stringify(data, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    downloadBlob(blob, `${filename}.json`)
  }

  function exportCSV(rows: Record<string, unknown>[], filename: string) {
    if (rows.length === 0) return
    const headers = Object.keys(rows[0])
    const csvRows = [
      headers.join(','),
      ...rows.map(row =>
        headers.map(h => {
          const val = row[h]
          const str = val === null || val === undefined ? '' : String(val)
          // Escape quotes and wrap in quotes if contains comma/quote/newline
          if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            return `"${str.replace(/"/g, '""')}"`
          }
          return str
        }).join(','),
      ),
    ]
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' })
    downloadBlob(blob, `${filename}.csv`)
  }

  return { exportJSON, exportCSV }
}
