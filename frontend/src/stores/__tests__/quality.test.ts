import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useQualityStore } from '../quality'

describe('useQualityStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should have correct initial state', () => {
    const store = useQualityStore()
    expect(store.loading).toBe(false)
  })

  it('should set loading state', () => {
    const store = useQualityStore()
    store.loading = true
    expect(store.loading).toBe(true)
  })
})
