import { createRouter, createWebHistory } from 'vue-router'

// 路由对应文档 §8.3 关键页面
const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/pages/Home.vue'),
    meta: { title: '全景图谱' },
  },
  {
    path: '/positions',
    name: 'position-list',
    component: () => import('@/pages/PositionList.vue'),
    meta: { title: '岗位列表' },
  },
  {
    path: '/position/:name',
    name: 'position-detail',
    component: () => import('@/pages/PositionDetail.vue'),
    meta: { title: '岗位详情' },
  },
  {
    path: '/match',
    name: 'match',
    component: () => import('@/pages/MatchDiagnosis.vue'),
    meta: { title: '匹配诊断' },
  },
  {
    path: '/evolution',
    name: 'evolution',
    component: () => import('@/pages/EvolutionDashboard.vue'),
    meta: { title: '演化看板' },
  },
  {
    path: '/quality',
    name: 'quality',
    component: () => import('@/pages/QualityDashboard.vue'),
    meta: { title: '图谱质量' },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/pages/Admin.vue'),
    meta: { title: '管理后台' },
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
