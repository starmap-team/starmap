import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/api/request'
import { useResponseValidation } from '@/validation'
// PLAN-014: 契约 schema（后端 Pydantic 导出，脚本生成；供 DEV 响应校验）
import positionSchema from '@contracts/schemas/position.schema.json'
import extractSchema from '@contracts/schemas/extract.schema.json'
import graphSchema from '@contracts/schemas/graph.schema.json'

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
  // fix: 后端 extract.py 已透传 4 个原丢弃字段 + 3 个反幻觉字段
  tools?: { skill?: string; name?: string; category?: string; proficiency?: string }[]
  learning_resources?: { title?: string; type?: string; url?: string }[]
  evolves_to?: string[]
  hallucinated_skills?: string[]
  missing_skills?: string[]
  issues?: string[]
  // 透明化：实际用于抽取的模型（含降级 fallback），用于“本次所用模型/降级”提示
  model_used?: string | null
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
  name_cn?: string
  industry: string
  description: string
  skills_required: { skill_id: string; name: string; category: string; confidence: number; source_count: number }[]
  discovered_at: string | null
  // review workflow — these fields are only populated when the
  // caller requests `?include_all=true` (admin). Public /positions endpoint
  // filters to approved only and may omit these.
  review_status?: 'draft' | 'pending_review' | 'approved' | 'rejected'
  created_by?: string | null
  reviewed_by?: string | null
  reviewed_at?: string | null
  rejection_reason?: string | null
}

export type ReviewStatusFilter = 'draft' | 'pending_review' | 'approved' | 'rejected' | 'all'

/** Default page size for position list queries */
const DEFAULT_PAGE_SIZE = 100

export const useJdStore = defineStore('jd', () => {
  const list = ref<JdRaw[]>([])
  const loading = ref(false)

  // PLAN-014: DEV 响应结构校验（失败仅 warn，不阻断业务）
  const { validateResponse } = useResponseValidation()

  async function fetchList() {
    loading.value = true
    try {
      const data = validateResponse(
        await request.get('/positions', { params: { page_size: DEFAULT_PAGE_SIZE } }) as PositionListResponse,
        positionSchema, '/positions', 'PositionListResponse',
      )
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

  /**
   * @deprecated 已被 fetchPositionDetail 取代（后端 /positions/{id} 返回完整
   * skills_required）。保留仅防外部引用破坏——新代码请用 fetchPositionDetail。
   */
  async function fetchPositionSkills(positionName: string) {
    const data = await request.get(`/graph/position/${encodeURIComponent(positionName)}/skills`)
    return validateResponse(data, graphSchema, '/graph/position/{name}/skills', 'PositionSkillDetailResponse')
  }

  /** Fetch position detail from PostgreSQL (accepts id or name; silent 抑制全局错误 toast) */
  async function fetchPositionDetail(positionName: string, opts?: { silent?: boolean }) {
    const data = await request.get(`/positions/${encodeURIComponent(positionName)}`, { silent: opts?.silent } as never)
    return validateResponse(data, positionSchema, '/positions/{id}', 'PositionNode')
  }

  /** Fetch paginated positions list
   *
   * `status` is forwarded to the backend. Public callers leave
   * it undefined and receive only approved positions. Admin can pass
   * `status: 'pending_review'` etc. to view other lifecycle states.
   */
  async function fetchPositions(
    params: { page?: number; page_size?: number; search?: string; industry?: string; status?: ReviewStatusFilter; include_all?: boolean } = {},
  ): Promise<PositionListResponse> {
    const query: Record<string, string | number | boolean> = {
      page: params.page ?? 1,
      page_size: params.page_size ?? DEFAULT_PAGE_SIZE,
    }
    if (params.search) query.search = params.search
    if (params.industry) query.industry = params.industry
    if (params.include_all) query.include_all = true
    if (params.status && params.status !== 'all') query.status = params.status
    const data = await request.get('/positions', { params: query }) as PositionListResponse
    return validateResponse(data, positionSchema, '/positions', 'PositionListResponse')
  }

  /** Fetch all distinct industries from backend (US-3: 完整行业列表) */
  async function fetchIndustries(): Promise<string[]> {
    const data = await request.get('/positions/industries') as { industries: string[] }
    return data.industries
  }

  /** Search positions by keyword, returns dropdown-ready items */
  async function searchPositions(keyword?: string) {
    const params: Record<string, string | number> = { page_size: 10 }  // 下拉搜索只需少量结果
    if (keyword?.trim()) {
      params.search = keyword.trim()
    }
    const data = validateResponse(
      await request.get('/positions', { params }) as PositionListResponse,
      positionSchema, '/positions', 'PositionListResponse',
    )
    return data.items.map(p => ({
      label: p.name_cn || p.name,
      value: p.name_cn || p.name,
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
      const data = validateResponse(
        // 本地降级模型抽取慢（40-120s+），与后端 Ollama 超时(300s)对齐，避免前端先超时
        await request.post('/extract/jd', { jd_content: jdContent }, { timeout: 300000 }) as JDExtractResult,
        extractSchema, '/extract/jd', 'ExtractionResult',
      )
      extractResult.value = data
      return data
    } catch (err: unknown) {
      // fix: HTTPException.detail 在 axios 错误对象里位于 response.data.detail，message 字段是 axios 默认文案
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const msg = detail ?? (err instanceof Error ? err.message : 'JD 抽取失败')
      throw new Error(msg)
    } finally {
      extractLoading.value = false
    }
  }

  // ── Cost summary ──
  async function fetchCostSummary(): Promise<unknown> {
    return await request.get('/extract/cost-summary')
  }

  function clearResult() {
    extractResult.value = null
  }

  return {
    list, loading, fetchList, fetchPositionSkills, fetchPositionDetail, fetchPositions,
    fetchIndustries, searchPositions, extractResult, extractLoading, extractJd, fetchCostSummary, clearResult,
  }
})
