/**
 * Data source types — shared across pipeline and datasource stores
 * DataSourceDetail is the canonical type (superset of the old DataSource)
 */

export interface DataSourceDetail {
  id: string
  name: string
 // 后端 Literal 为 job_board|blog|esco|manual|rss|api；保留 crawler/import 等
 // 历史值以兼容 DataSourceManager.vue 等消费方（superset 补齐，见 datasource 优化设计需求 D）
  source_type: 'crawler' | 'api' | 'manual' | 'import' | 'job_board' | 'blog' | 'esco' | 'rss'
  authority_score: number
  status: 'active' | 'paused' | 'inactive' | 'error'
  last_crawl_at: string | null
  total_records: number
  valid_records: number
  duplicate_rate: number
  avg_quality_score: number
  config?: Record<string, unknown>
  has_adapter?: boolean
  adapter_platform?: string | null
}
