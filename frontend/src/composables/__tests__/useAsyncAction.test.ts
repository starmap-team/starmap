import { describe, it, expect } from 'vitest'
import { useAsyncAction } from '../useAsyncAction'

describe('useAsyncAction', () => {
  it('should start with loading=false and error=null', () => {
    const { loading, error } = useAsyncAction()
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('should set loading=true during execution', async () => {
    const { loading, execute } = useAsyncAction()
    let resolveFn: (value: string) => void
    const pending = new Promise<string>(resolve => { resolveFn = resolve })

    const promise = execute(() => pending)
    expect(loading.value).toBe(true)

    resolveFn!('done')
    await promise
    expect(loading.value).toBe(false)
  })

  it('should return result on success', async () => {
    const { execute } = useAsyncAction()
    const result = await execute(() => Promise.resolve('hello'))
    expect(result).toBe('hello')
  })

  it('should set error on failure and return undefined', async () => {
    const { error, execute } = useAsyncAction()
    const result = await execute(() => Promise.reject(new Error('boom')))
    expect(result).toBeUndefined()
    expect(error.value).toBe('boom')
  })

  it('should clear error on next successful call', async () => {
    const { error, execute } = useAsyncAction()
    await execute(() => Promise.reject(new Error('fail')))
    expect(error.value).toBe('fail')
    await execute(() => Promise.resolve('ok'))
    expect(error.value).toBeNull()
  })

  it('should handle non-Error throwables', async () => {
    const { error, execute } = useAsyncAction()
    await execute(() => Promise.reject('string error'))
    expect(error.value).toBe('string error')
  })

  it('should clear error via clearError', async () => {
    const { error, execute, clearError } = useAsyncAction()
    await execute(() => Promise.reject(new Error('fail')))
    expect(error.value).toBe('fail')
    clearError()
    expect(error.value).toBeNull()
  })

  it('should reset loading to false even on failure', async () => {
    const { loading, execute } = useAsyncAction()
    await execute(() => Promise.reject(new Error('fail')))
    expect(loading.value).toBe(false)
  })
})
