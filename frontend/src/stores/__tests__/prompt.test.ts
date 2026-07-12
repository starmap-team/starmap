import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePromptStore } from '../prompt'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('usePromptStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should have correct initial state', () => {
    const store = usePromptStore()
    expect(store.prompts).toEqual({})
    expect(store.currentTemplate).toBe('')
    expect(store.abResults).toEqual({})
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('should fetch prompts and update state', async () => {
    const request = (await import('@/api/request')).default
    const mockData = {
      jd_extraction: {
        versions: ['v1', 'v2'],
        active: 'v1',
        ab_test: null,
      },
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockData)

    const store = usePromptStore()
    await store.fetchPrompts()

    expect(store.prompts).toEqual(mockData)
    expect(store.loading).toBe(false)
    expect(request.get).toHaveBeenCalledWith('/admin/prompts')
  })

  it('should handle fetch prompts error', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockRejectedValueOnce(new Error('Network error'))

    const store = usePromptStore()
    await store.fetchPrompts()

    expect(store.error).toBe('Network error')
    expect(store.loading).toBe(false)
  })

  it('should fetch template content', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce({ template: 'Extract skills from: $jd_content' })

    const store = usePromptStore()
    await store.fetchTemplate('jd_extraction')

    expect(store.currentTemplate).toBe('Extract skills from: $jd_content')
    expect(request.get).toHaveBeenCalledWith('/admin/prompts/jd_extraction/template')
  })

  it('should fetch template with specific version', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.get).mockResolvedValueOnce({ template: 'v2 template' })

    const store = usePromptStore()
    await store.fetchTemplate('jd_extraction', 'v2')

    expect(store.currentTemplate).toBe('v2 template')
    expect(request.get).toHaveBeenCalledWith('/admin/prompts/jd_extraction/template?version=v2')
  })

  it('should switch active version', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.put).mockResolvedValueOnce({})
    vi.mocked(request.get).mockResolvedValueOnce({ jd_extraction: { versions: ['v1', 'v2'], active: 'v2', ab_test: null } })

    const store = usePromptStore()
    await store.switchActiveVersion('jd_extraction', 'v2')

    expect(request.put).toHaveBeenCalledWith('/admin/prompts/jd_extraction/active', { version: 'v2' })
  })

  it('should register new version', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({})
    vi.mocked(request.get).mockResolvedValueOnce({})

    const store = usePromptStore()
    await store.registerVersion('jd_extraction', 'test template', 'v_test', false)

    expect(request.post).toHaveBeenCalledWith('/admin/prompts/jd_extraction/versions', {
      template: 'test template',
      version: 'v_test',
      activate: false,
    })
  })

  it('should start A/B test', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({})
    vi.mocked(request.get).mockResolvedValueOnce({})

    const store = usePromptStore()
    await store.startABTest('jd_extraction', 'v2', 0.2)

    expect(request.post).toHaveBeenCalledWith('/admin/prompts/jd_extraction/ab-test', {
      canary_version: 'v2',
      traffic_fraction: 0.2,
    })
  })

  it('should stop A/B test', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.delete).mockResolvedValueOnce({})
    vi.mocked(request.get).mockResolvedValueOnce({})

    const store = usePromptStore()
    await store.stopABTest('jd_extraction')

    expect(request.delete).toHaveBeenCalledWith('/admin/prompts/jd_extraction/ab-test')
  })

  it('should fetch A/B results', async () => {
    const request = (await import('@/api/request')).default
    const mockResults = {
      versions: {
        v1: { count: 10, success_rate: 0.8, avg_f1: 0.75, avg_latency_ms: 120 },
      },
    }
    vi.mocked(request.get).mockResolvedValueOnce(mockResults)

    const store = usePromptStore()
    await store.fetchABResults('jd_extraction')

    expect(store.abResults).toEqual(mockResults.versions)
  })
})