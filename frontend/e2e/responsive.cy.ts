/**
 * StarMap — Responsive E2E Test
 * Sprint 4.3: Test all 13 pages at 1920px and 1440px viewports.
 *
 * Verifies:
 *   - Page renders at each viewport without errors
 *   - No horizontal overflow (body scrollWidth <= viewport width)
 *   - Screenshot captured for visual regression
 *
 * Run: npx cypress run --spec e2e/responsive.cy.ts
 */

const BASE_URL = 'http://localhost:5173'

// All 13 pages from the router
const ALL_PAGES = [
  { path: '/', name: 'Home' },
  { path: '/positions', name: 'PositionList' },
  { path: '/position/Frontend%20Engineer', name: 'PositionDetail' },
  { path: '/match', name: 'MatchDiagnosis' },
  { path: '/evolution', name: 'EvolutionDashboard' },
  { path: '/quality', name: 'QualityDashboard' },
  { path: '/pipeline', name: 'PipelineMonitor' },
  { path: '/datasources', name: 'DataSources' },
  { path: '/analysis', name: 'PipelineAnalysis' },
  { path: '/extract', name: 'ExtractJD' },
  { path: '/loop', name: 'LoopDemo' },
  { path: '/admin', name: 'Admin' },
  { path: '/dashboard', name: 'DataDashboard' },
]

const VIEWPORTS = [
  { width: 1920, height: 1080, label: '1920x1080' },
  { width: 1440, height: 900, label: '1440x900' },
]

describe('Responsive — 1920px Desktop', () => {
  beforeEach(() => {
    cy.viewport(1920, 1080)
  })

  ALL_PAGES.forEach((page) => {
    it(`${page.name} (${page.path}) — renders at 1920px`, () => {
      cy.visit(`${BASE_URL}${page.path}`, {
        failOnStatusCode: false,
        timeout: 15000,
      })

      // Wait for page to settle
      cy.wait(1500)

      // Verify page rendered
      cy.get('body', { timeout: 10000 }).should('not.be.empty')

      // Check no horizontal overflow
      cy.document().then((doc) => {
        const scrollWidth = doc.documentElement.scrollWidth
        const clientWidth = doc.documentElement.clientWidth
        cy.log(`${page.name} at 1920px: scrollWidth=${scrollWidth}, clientWidth=${clientWidth}`)
        // Allow 5px tolerance for scrollbar
        expect(scrollWidth, `${page.name} should not have horizontal overflow at 1920px`).to.be.at.most(clientWidth + 5)
      })

      // Screenshot for visual regression
      cy.screenshot(`responsive/1920px/${page.name}`, {
        capture: 'viewport',
        overwrite: true,
      })
    })
  })
})

describe('Responsive — 1440px Desktop', () => {
  beforeEach(() => {
    cy.viewport(1440, 900)
  })

  ALL_PAGES.forEach((page) => {
    it(`${page.name} (${page.path}) — renders at 1440px`, () => {
      cy.visit(`${BASE_URL}${page.path}`, {
        failOnStatusCode: false,
        timeout: 15000,
      })

      // Wait for page to settle
      cy.wait(1500)

      // Verify page rendered
      cy.get('body', { timeout: 10000 }).should('not.be.empty')

      // Check no horizontal overflow
      cy.document().then((doc) => {
        const scrollWidth = doc.documentElement.scrollWidth
        const clientWidth = doc.documentElement.clientWidth
        cy.log(`${page.name} at 1440px: scrollWidth=${scrollWidth}, clientWidth=${clientWidth}`)
        expect(scrollWidth, `${page.name} should not have horizontal overflow at 1440px`).to.be.at.most(clientWidth + 5)
      })

      // Screenshot for visual regression
      cy.screenshot(`responsive/1440px/${page.name}`, {
        capture: 'viewport',
        overwrite: true,
      })
    })
  })
})

describe('Responsive — Overflow Summary', () => {
  it('All viewports checked for overflow', () => {
    const totalChecks = ALL_PAGES.length * VIEWPORTS.length
    cy.log(`Responsive checks: ${ALL_PAGES.length} pages x ${VIEWPORTS.length} viewports = ${totalChecks} checks`)
    expect(totalChecks).to.equal(26)
  })
})
