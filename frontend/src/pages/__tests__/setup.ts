/**
 * A page-level setup file is NOT used as a vitest setupFiles entry
 * (to avoid polluting non-page tests with module-level mocks).
 *
 * Each page spec file should do its own vi.mock() calls inline.
 * This file exists only as documentation of the shared mock strategy.
 *
 * See helpers.ts for the renderPage() wrapper used by all page specs.
 */
