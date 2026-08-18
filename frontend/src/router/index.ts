import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ensureBootstrapped } from '@/composables/useAuthBootstrap'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/pages/Home.vue'),
    meta: { title: '全景图谱', icon: 'Connection', breadcrumb: ['首页', '全景图谱'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/positions',
    name: 'position-list',
    component: () => import('@/pages/PositionList.vue'),
    meta: { title: '岗位列表', icon: 'User', breadcrumb: ['首页', '岗位列表'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/position/:name',
    name: 'position-detail',
    component: () => import('@/pages/PositionDetail.vue'),
    meta: { title: '岗位详情', icon: 'User', breadcrumb: ['首页', '岗位列表', '岗位详情'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/match',
    name: 'match',
    component: () => import('@/pages/MatchDiagnosis.vue'),
    meta: { title: '匹配诊断', icon: 'Monitor', breadcrumb: ['首页', '匹配诊断'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/evolution',
    name: 'evolution',
    component: () => import('@/pages/EvolutionDashboard.vue'),
    meta: { title: '演化看板', icon: 'TrendCharts', breadcrumb: ['首页', '演化看板'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/quality',
    name: 'quality',
    component: () => import('@/pages/QualityDashboard.vue'),
    meta: { title: '图谱质量', icon: 'DataAnalysis', breadcrumb: ['首页', '图谱质量'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/pipeline',
    name: 'pipeline',
    component: () => import('@/pages/PipelineMonitor.vue'),
    meta: { title: '数据流水线', icon: 'DataLine', breadcrumb: ['首页', '数据流水线'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/datasources',
    name: 'datasources',
    component: () => import('@/pages/DataSources.vue'),
    meta: { title: '数据源管理', icon: 'Coin', breadcrumb: ['首页', '数据源管理'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/analysis',
    name: 'jobseeker-analysis',
    component: () => import('@/pages/PipelineAnalysis.vue'),
    meta: { title: '求职者分析', icon: 'User', breadcrumb: ['首页', '求职者分析'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/extract',
    name: 'extract',
    component: () => import('@/pages/ExtractJD.vue'),
    meta: { title: 'JD 抽取', icon: 'Document', breadcrumb: ['首页', 'JD 抽取'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/loop',
    name: 'loop-demo',
    component: () => import('@/pages/LoopDemo.vue'),
    meta: { title: '闭环演示', icon: 'Refresh', breadcrumb: ['首页', '闭环演示'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/Login.vue'),
    meta: { title: '登录', transition: 'page-slide' },
  },
  {
    path: '/change-password',
    name: 'change-password',
    component: () => import('@/pages/ChangePassword.vue'),
    meta: { title: '修改密码', transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/pages/Admin.vue'),
    meta: { title: '管理后台', icon: 'Setting', breadcrumb: ['首页', '管理后台'], transition: 'page-slide', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/dashboard',
    name: 'data-dashboard',
    component: () => import('@/pages/DataDashboard.vue'),
    meta: { title: '数据大屏', icon: 'Odometer', breadcrumb: ['首页', '数据大屏'], transition: 'page-slide', requiresAuth: true },
  },
  {
    path: '/learning',
    name: 'learning',
    component: () => import('@/pages/LearningCenter.vue'),
    meta: { title: '学习中心', icon: 'Reading', breadcrumb: ['首页', '学习中心'], transition: 'page-slide', requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? '星图'} | StarMap`
})

// ---------------------------------------------------------------------------
// Auth guard — async bootstrap + must_change_password enforcement
// ---------------------------------------------------------------------------
const PUBLIC_PATHS = new Set<string>(['/login', '/change-password'])

function hasTokens(): boolean {
  try {
    return Boolean(localStorage.getItem('starmap_access_token'))
      || Boolean(localStorage.getItem('starmap_refresh_token'))
  } catch {
    return false
  }
}

router.beforeEach(async (to) => {
 // Skip guard for public paths
  if (PUBLIC_PATHS.has(to.path)) {
    return true
  }
  const requiresAuth = (to.meta as { requiresAuth?: boolean }).requiresAuth === true
  const requiresAdmin = (to.meta as { requiresAdmin?: boolean }).requiresAdmin === true

 // No tokens at all — redirect to login for auth-required pages.
  if (!hasTokens()) {
    if (requiresAuth) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
    return true
  }

 // Tokens exist — wait for silent-refresh bootstrap to settle before
 // checking auth state, so we don't race between localStorage read and
 // the async /auth/refresh call.
  const booted = await ensureBootstrapped()
  if (!booted) {
    const userStore = useUserStore()
    userStore.clearUser()
    if (requiresAuth) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
    return true
  }

 // ── must_change_password enforcement ──
  if (requiresAuth) {
    const userStore = useUserStore()
    if (userStore.mustChangePassword) {
      return {
        path: '/change-password',
        query: { forced: '1', redirect: to.fullPath },
      }
    }
  }

 // ── Admin guard ──
  if (requiresAdmin) {
    const userStore = useUserStore()
    if (!userStore.isAdmin) {
      return { path: '/' }
    }
  }

  return true
})

// Listen for 401 events emitted by api/request.ts and route to /login.
window.addEventListener('auth:unauthorized', () => {
 // Clear user state on 401. We use clearUser (local-only) instead of logout
 // because refresh-token revocation requires an extra round-trip and the user
 // is being redirected away anyway.
  const userStore = useUserStore()
  userStore.clearUser()
  if (router.currentRoute.value.path !== '/login') {
    router.push({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
  }
})

export default router
