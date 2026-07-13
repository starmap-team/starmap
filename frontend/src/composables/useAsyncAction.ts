/**
 * useAsyncAction — 统一 loading/error 模式的 composable
 *
 * 用法：
 * ```ts
 * const { loading, error, execute } = useAsyncAction()
 * const result = await execute(() => someAsyncCall())
 * ```
 */
import { ref } from 'vue'

export function useAsyncAction() {
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function execute<T>(fn: () => Promise<T>): Promise<T | undefined> {
    loading.value = true
    error.value = null
    try {
      return await fn()
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      error.value = message
      return undefined
    } finally {
      loading.value = false
    }
  }

  function clearError() {
    error.value = null
  }

  return { loading, error, execute, clearError }
}
