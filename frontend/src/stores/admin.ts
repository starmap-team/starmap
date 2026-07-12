/**
 * Admin store — backward-compatible re-export.
 *
 * Phase 7 refactor: The monolithic admin store has been split into:
 *   - useDataSourceStore  (frontend/src/stores/datasource.ts)
 *   - useAuditStore       (frontend/src/stores/audit.ts)
 *   - useGraphNodeStore   (frontend/src/stores/graphNode.ts)
 *
 * This module re-exports useDataSourceStore as useAdminStore for backward
 * compatibility. Consumers should migrate to the dedicated stores above.
 *
 * @deprecated Migrate to useAuditStore or useGraphNodeStore directly.
 */
export { useDataSourceStore as useAdminStore } from '@/stores/datasource'
export type { AuditItem } from '@/stores/audit'
export type { GraphNodeItem } from '@/composables/useGraphNodeList'