import { defineStore } from 'pinia'
import { ref } from 'vue'

/** JD 原始数据 store */
export interface JdRaw {
  id: number
  source: string
  title: string
  company: string
  content: string
  city: string
  salary_min: number
  salary_max: number
  publish_date: string
}

export const useJdStore = defineStore('jd', () => {
  const list = ref<JdRaw[]>([])
  const loading = ref(false)

  async function fetchList() {
    loading.value = true
    try {
      const resp = await fetch('/api/v1/jd/list')
      const data = await resp.json()
      list.value = data.items ?? []
    } finally {
      loading.value = false
    }
  }

  return { list, loading, fetchList }
})
