/**
 * Deprecated: use `@/stores/datasource` instead.
 * This module re-exports useDataSourceStore as useAdminStore for backward compatibility.
 * Will be removed in a future phase — migrate consumers to useDataSourceStore.
 */
export { useDataSourceStore as useAdminStore } from '@/stores/datasource'
export type { AuditItem } from '@/stores/datasource'
