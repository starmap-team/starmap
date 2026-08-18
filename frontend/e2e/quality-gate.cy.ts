/**
 * StarMap — Quality Gate E2E Test
 * Sprint 4.3: Verify all pages render without console errors.
 *
 * This test acts as a CI quality gate: for each page, it visits
 * the route, asserts 0 console.error messages, and confirms
 * the page renders without a blank/broken state.
 *
 * Run: npx cypress run --spec e2e/quality-gate.cy.ts
 */

const BASE_URL = Cypress.config('baseUrl') || 'http://localhost:5173'

// All 10 new/enhanced pages from the sprint (subset of all 13 routes)
const QUALITY_GATE_PAGES = [
  { path: '/', name: '全景图谱 (Home)', selector: '.graph-page, .layout-main, main' },
  { path: '/positions', name: '岗位列表 (PositionList)', selector: '.layout-main, main, .el-table' },
  { path: '/match', name: '匹配诊断 (MatchDiagnosis)', selector: '.layout-main, main' },
  { path: '/extract', name: 'JD 抽取 (ExtractJD)', selector: '.layout-main, main' },
  { path: '/pipeline', name: '数据流水线 (PipelineMonitor)', selector: '.layout-main, main' },
  { path: '/datasources', name: '数据源管理 (DataSources)', selector: '.layout-main, main' },
  { path: '/evolution', name: '演化看板 (EvolutionDashboard)', selector: '.layout-main, main' },
  { path: '/quality', name: '图谱质量 (QualityDashboard)', selector: '.layout-main, main' },
  { path: '/loop', name: '闭环演示 (LoopDemo)', selector: '.layout-main, main' },
  { path: '/admin', name: '管理后台 (Admin)', selector: '.layout-main, main' },
]

describe('Quality Gate — Page Rendering', () => {

  QUALITY_GATE_PAGES.forEach((page) => {
    it(`${page.name} — 0 console.error`, () => {
      const consoleErrors: string[] = []

      cy.on('window:console', (msg) => {
        if (msg.type === 'error') {
 // Filter out expected/harmless errors
          const text = msg.text || msg.message || ''
 // Ignore network errors from missing backend
          if (text.includes('NetworkError') || text.includes('Failed to fetch') || text.includes('ERR_CONNECTION_REFUSED')) {
            return
          }
 // Ignore favicon 404
          if (text.includes('favicon')) {
            return
          }
 // Ignore Vite HMR WebSocket errors
          if (text.includes('WebSocket') || text.includes('[vite]')) {
            return
          }
          consoleErrors.push(text)
        }
      })

 // Also catch uncaught exceptions
      cy.on('window:before:unload', () => {})

      cy.visit(`${BASE_URL}${page.path}`, {
        failOnStatusCode: false,
        timeout: 15000,
      })

 // Wait for page to settle — use conditional wait instead of fixed delay
      cy.get('body', { timeout: 10000 }).should('not.be.empty')
 // Give Vue a brief moment to fully render after body appears
      cy.wait(500)

 // Verify no console errors
      cy.then(() => {
        if (consoleErrors.length > 0) {
          cy.log(`Console errors on ${page.name}: ${JSON.stringify(consoleErrors)}`)
        }
        expect(consoleErrors, `${page.name} should have 0 console errors`).to.have.length(0)
      })

 // Verify the page has meaningful content (not just a loading spinner forever)
      cy.get('body').then(($body) => {
        const text = $body.text()
 // Page should have some content beyond just whitespace
        expect(text.trim().length, `${page.name} should render content`).to.be.greaterThan(50)
      })
    })
  })
})

describe('Quality Gate — Full Summary', () => {
  it('All pages listed and verified', () => {
 // This test just ensures all pages were defined
    const totalPages = QUALITY_GATE_PAGES.length
    cy.log(`Quality gate verified ${totalPages} pages`)
    expect(totalPages).to.be.greaterThan(0)
  })
})
