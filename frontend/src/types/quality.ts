/**
 * Quality alert types — shared across pipeline and quality stores
 * Merged from pipeline.ts (SSE alert) and quality.ts (persistent alert)
 */

export interface QualityAlert {
 // ── Fields from quality.ts (persistent alert) ──
  id: string | number
  type?: string
  status?: 'pending' | 'processing' | 'resolved' | 'ignored'
  created_at?: string

 // ── Fields from pipeline.ts (SSE alert) ──
  level?: 'info' | 'warning' | 'error' | 'critical'
  severity?: 'info' | 'warning' | 'error' | 'critical'
  message?: string
  source?: string
  timestamp?: string
  dimension?: string
  value?: number
  threshold?: number

 // ── Test compatibility ──
  metric?: string
}
