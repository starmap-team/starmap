/**
 * ECharts lazy-loading plugin — defers ECharts module registration until first use.
 *
 * Instead of eagerly importing and registering all ECharts modules at app startup
 * (which adds ~200KB to the initial bundle), this plugin:
 * 1. Registers a stub VChart component that triggers lazy loading on mount
 * 2. On first render, dynamically imports the ECharts modules and registers them
 * 3. Replaces the stub with the real vue-echarts VChart component
 *
 * Usage in main.ts:
 * import { useEChartsLazy } from '@/plugins/echarts'
 * app.use(useEChartsLazy)
 *
 * Pages that need additional chart types (e.g. TreemapChart, GaugeChart) can
 * still call `use([...])` directly — those modules will be loaded eagerly by
 * the page's own import, which is fine since they are code-split at the route level.
 */
import type { App, Plugin } from 'vue'
import { defineAsyncComponent, shallowRef } from 'vue'

/** Tracks whether the core ECharts modules have been registered. */
const registered = shallowRef(false)

/**
 * Dynamically import and register the core ECharts modules.
 * Called once on first VChart mount; subsequent calls are no-ops.
 */
async function ensureRegistered(): Promise<void> {
  if (registered.value) return

  const [
    { use },
    { CanvasRenderer },
    charts,
    components,
  ] = await Promise.all([
    import('echarts/core'),
    import('echarts/renderers'),
    import('echarts/charts'),
    import('echarts/components'),
  ])

  use([
    CanvasRenderer,
    charts.PieChart,
    charts.LineChart,
    charts.RadarChart,
    charts.BarChart,
    components.TitleComponent,
    components.TooltipComponent,
    components.LegendComponent,
    components.GridComponent,
    components.RadarComponent,
  ])

  registered.value = true
}

/**
 * Vue plugin that installs a lazy-loaded VChart component.
 *
 * On first mount it triggers the dynamic import of ECharts core modules,
 * then renders the real vue-echarts component. While loading, it renders
 * a minimal placeholder to avoid layout shift.
 */
export function useEChartsLazy(): Plugin {
  return {
    install(app: App) {
      const LazyVChart = defineAsyncComponent({
        loader: async () => {
          await ensureRegistered()
          const { default: VChart } = await import('vue-echarts')
          return VChart
        },
        loadingComponent: {
          template: '<div style="min-height:200px" />',
        },
      })

      app.component('VChart', LazyVChart)
    },
  }
}

export { registered, ensureRegistered }
