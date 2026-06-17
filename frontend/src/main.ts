import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, LineChart, RadarChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent, RadarComponent } from 'echarts/components'

import App from './App.vue'
import router from './router'
import { enableMocking } from './mock/msw-browser'

// ECharts 按需注册
use([CanvasRenderer, PieChart, LineChart, RadarChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, RadarComponent])

async function bootstrap() {
  // 开发环境启用 MSW mock，联调时注释掉此行
  await enableMocking()

  const app = createApp(App)
  app.use(createPinia())
  app.use(router)
  app.use(ElementPlus)

  // 全局注册 vue-echarts 组件，页面中直接用 <v-chart>
  app.component('VChart', VChart)

  app.mount('#app')
}

bootstrap()
