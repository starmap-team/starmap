import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

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
    component: () => import('@/components/ProfileMenu.vue'),
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
// Auth guard (Phase 8 — frontend UX fix 3)
// ---------------------------------------------------------------------------
// Routes can declare `meta: { requiresAuth: true }` to enforce that the
// requesting session is authenticated. Currently only `/admin` needs the
// guard — other routes degrade gracefully (login prompts surface via the
// global ElMessage in request.ts).
// ---------------------------------------------------------------------------
const PUBLIC_PATHS = new Set<string>(['/login'])

// Pinia store import is deferred to avoid Pinia<->router cycle: the auth
// bootstrap evaluates localStorage at module load time, which precedes
// Pinia install. We read a small "auth hint" synchronously here.

function isAuthed(): boolean {
  try {
    return Boolean(localStorage.getItem('starmap_access_token'))
  } catch {
    return false
  }
}

router.beforeEach((to) => {
  // Skip guard for public paths
  if (PUBLIC_PATHS.has(to.path) || to.path.startsWith('/login')) {
    return true
  }
  const requiresAuth = (to.meta as { requiresAuth?: boolean }).requiresAuth === true
  const requiresAdmin = (to.meta as { requiresAdmin?: boolean }).requiresAdmin === true

  // 检查认证
  if (requiresAuth && !isAuthed()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 检查 admin 权限
  if (requiresAdmin) {
    const userStore = useUserStore()
    if (!userStore.user) {
      userStore.initUser()
    }
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
