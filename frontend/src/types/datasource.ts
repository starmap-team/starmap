/**
 * Data source types — shared across pipeline and datasource stores
 * DataSourceDetail is the canonical type (superset of the old DataSource)
 */

export interface DataSourceDetail {
  id: string
  name: string
  source_type: 'crawler' | 'api' | 'manual' | 'import'
  authority_score: number
  status: 'active' | 'paused' | 'error'
  last_crawl_at: string
  total_records: number
  valid_records: number
  duplicate_rate: number
  avg_quality_score: number
  daily_crawl_volume: number[]
  config?: Record<string, unknown>
}
