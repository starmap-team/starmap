import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
// @ts-expect-error - element-plus locale module types
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import 'element-plus/dist/index.css'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, LineChart, RadarChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent, RadarComponent } from 'echarts/components'

import App from './App.vue'
import router from './router'

// ECharts 按需注册
use([CanvasRenderer, PieChart, LineChart, RadarChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, RadarComponent])

async function bootstrap() {
  const app = createApp(App)
  app.use(createPinia())
  app.use(router)
  app.use(ElementPlus, { locale: zhCn })

 // DEBUG: global error handler to capture full stack traces
  app.config.errorHandler = (err, instance, info) => {
    console.error('[Vue Global Error]', err)
    if (err instanceof Error) console.error('[Vue Global Error Stack]', err.stack)
    console.error('[Vue Global Error Instance]', instance?.$options?.name ?? instance?.$options?.__name ?? 'unknown')
    console.error('[Vue Global Error Info]', info)
  }

 // 全局注册 vue-echarts 组件，页面中直接用 <v-chart>
  app.component('VChart', VChart)

  app.mount('#app')
}

bootstrap()
