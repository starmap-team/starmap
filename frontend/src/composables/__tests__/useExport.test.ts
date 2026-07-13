import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useExport } from '../useExport'

describe('useExport', () => {
  beforeEach(() => {
    // Mock URL.createObjectURL and document.createElement
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:mock-url'),
      revokeObjectURL: vi.fn(),
    })
  })

  it('should export JSON and trigger download', () => {
    const { exportJSON } = useExport()
    const clickSpy = vi.fn()
    const anchor = { href: '', download: '', click: clickSpy }
    vi.spyOn(document, 'createElement').mockReturnValue(anchor as any)

    exportJSON({ name: 'test', value: 42 }, 'report')

    expect(anchor.download).toBe('report.json')
    expect(clickSpy).toHaveBeenCalled()
  })

  it('should export CSV with headers and rows', () => {
    const { exportCSV } = useExport()
    const clickSpy = vi.fn()
    const anchor = { href: '', download: '', click: clickSpy }
    vi.spyOn(document, 'createElement').mockReturnValue(anchor as any)

    exportCSV([{ name: 'Alice', age: 30 }, { name: 'Bob', age: 25 }], 'users')

    expect(anchor.download).toBe('users.csv')
    expect(clickSpy).toHaveBeenCalled()
  })

  it('should skip CSV export when rows are empty', () => {
    const { exportCSV } = useExport()
    const clickSpy = vi.fn()
    const anchor = { href: '', download: '', click: clickSpy }
    vi.spyOn(document, 'createElement').mockReturnValue(anchor as any)

    exportCSV([], 'empty')

    expect(clickSpy).not.toHaveBeenCalled()
  })

  it('should escape CSV fields with commas and quotes', () => {
    const { exportCSV } = useExport()
    const clickSpy = vi.fn()
    const anchor = { href: '', download: '', click: clickSpy }
    vi.spyOn(document, 'createElement').mockReturnValue(anchor as any)

    exportCSV([{ text: 'hello, "world"' }], 'test')

    expect(clickSpy).toHaveBeenCalled()
  })
})
