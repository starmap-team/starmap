import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'

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
      // 使用真实后端 /positions 端点（JD 数据已导入 position_records）
      const data = await request.get('/positions', { params: { page_size: 100 } })
      const items = (data as any).items ?? (data as any) ?? []
      list.value = items.map((p: any) => ({
        id: p.position_id ?? p.id ?? 0,
        source: 'database',
        title: p.name ?? p.title ?? '',
        company: '',
        content: p.description ?? '',
        city: '',
        salary_min: 0,
        salary_max: 0,
        publish_date: p.created_at ?? '',
      }))
    } finally {
      loading.value = false
    }
  }

  return { list, loading, fetchList }
})
