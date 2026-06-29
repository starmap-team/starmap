import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/pages/Home.vue'),
    meta: { title: '全景图谱', icon: 'Connection', breadcrumb: ['首页', '全景图谱'], transition: 'page-slide' },
  },
  {
    path: '/positions',
    name: 'position-list',
    component: () => import('@/pages/PositionList.vue'),
    meta: { title: '岗位列表', icon: 'User', breadcrumb: ['首页', '岗位列表'], transition: 'page-slide' },
  },
  {
    path: '/position/:name',
    name: 'position-detail',
    component: () => import('@/pages/PositionDetail.vue'),
    meta: { title: '岗位详情', icon: 'User', breadcrumb: ['首页', '岗位列表', '岗位详情'], transition: 'page-slide' },
  },
  {
    path: '/match',
    name: 'match',
    component: () => import('@/pages/MatchDiagnosis.vue'),
    meta: { title: '匹配诊断', icon: 'Monitor', breadcrumb: ['首页', '匹配诊断'], transition: 'page-slide' },
  },
  {
    path: '/evolution',
    name: 'evolution',
    component: () => import('@/pages/EvolutionDashboard.vue'),
    meta: { title: '演化看板', icon: 'TrendCharts', breadcrumb: ['首页', '演化看板'], transition: 'page-slide' },
  },
  {
    path: '/quality',
    name: 'quality',
    component: () => import('@/pages/QualityDashboard.vue'),
    meta: { title: '图谱质量', icon: 'DataAnalysis', breadcrumb: ['首页', '图谱质量'], transition: 'page-slide' },
  },
  {
    path: '/extract',
    name: 'extract',
    component: () => import('@/pages/ExtractJD.vue'),
    meta: { title: 'JD 抽取', icon: 'Document', breadcrumb: ['首页', 'JD 抽取'], transition: 'page-slide' },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/pages/Admin.vue'),
    meta: { title: '管理后台', icon: 'Setting', breadcrumb: ['首页', '管理后台'], transition: 'page-slide' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? '星图'} | StarMap`
})

export default router
