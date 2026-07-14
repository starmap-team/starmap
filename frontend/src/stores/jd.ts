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

/** JD extraction result from /extract/jd */
interface JDExtractResult {
  position_name?: string
  required_skills?: { skill?: string; name?: string; category?: string; proficiency?: string }[]
  preferred_skills?: { skill?: string; name?: string; category?: string; proficiency?: string }[]
  experience_required?: number | null
  education_required?: string | null
  responsibilities?: string[]
  confidence?: number
  hallucination_score?: number | null
  normalized_skills?: { original?: string; normalized?: string; method?: string; confidence?: number }[]
  skills?: { name: string; category: string; confidence: number; is_new: boolean }[]
  position?: string
  [key: string]: unknown
}

/** Backend PositionListResponse shape — matches /positions endpoint */
interface PositionListResponse {
  items: PositionItem[]
  total: number
  page: number
  page_size: number
}

interface PositionItem {
  position_id: string
  name: string
  industry: string
  description: string
  skills_required: { skill_id: string; name: string; category: string; confidence: number; source_count: number }[]
  discovered_at: string | null
}

/** Default page size for position list queries */
const DEFAULT_PAGE_SIZE = 100

export const useJdStore = defineStore('jd', () => {
  const list = ref<JdRaw[]>([])
  const loading = ref(false)

  async function fetchList() {
    loading.value = true
    try {
      const data = await request.get('/positions', { params: { page_size: DEFAULT_PAGE_SIZE } }) as PositionListResponse
      list.value = data.items.map(p => ({
        id: 0, // position_id is a UUID string, not a numeric id
        source: 'database',
        title: p.name ?? '',
        company: p.industry ?? '',
        content: p.description ?? '',
        city: '',
        salary_min: 0,
        salary_max: 0,
        publish_date: p.discovered_at ?? '',
      }))
    } finally {
      loading.value = false
    }
  }

  /** Fetch position skills from Neo4j (with PostgreSQL fallback) */
  async function fetchPositionSkills(positionName: string) {
    return request.get(`/graph/position/${encodeURIComponent(positionName)}/skills`)
  }

  /** Fetch position detail from PostgreSQL */
  async function fetchPositionDetail(positionName: string) {
    return request.get(`/positions/${encodeURIComponent(positionName)}`)
  }

  /** Fetch paginated positions list */
  async function fetchPositions(params: { page?: number; page_size?: number } = {}): Promise<PositionListResponse> {
    return request.get('/positions', {
      params: { page: params.page ?? 1, page_size: params.page_size ?? DEFAULT_PAGE_SIZE },
    }) as Promise<PositionListResponse>
  }

  /** Search positions by keyword, returns dropdown-ready items */
  async function searchPositions(keyword?: string) {
    const params: Record<string, string | number> = { page_size: DEFAULT_PAGE_SIZE }
    if (keyword?.trim()) {
      params.search = keyword.trim()
    }
    const data = await request.get('/positions', { params }) as PositionListResponse
    return data.items.map(p => ({
      label: p.name,
      value: p.name,
      position_id: p.position_id,
    }))
  }

  // ── JD Extraction (migrated from ExtractJD.vue — M23) ──
  const extractResult = ref<JDExtractResult | null>(null)
  const extractLoading = ref(false)

  async function extractJd(jdContent: string) {
    extractLoading.value = true
    extractResult.value = null
    try {
      const data = await request.post('/extract/jd', { jd_content: jdContent }, { timeout: 120000 }) as JDExtractResult
      extractResult.value = data
      return data
    } finally {
      extractLoading.value = false
    }
  }

  function clearResult() {
    extractResult.value = null
  }

  return { list, loading, fetchList, fetchPositionSkills, fetchPositionDetail, fetchPositions, searchPositions, extractResult, extractLoading, extractJd, clearResult }
})
