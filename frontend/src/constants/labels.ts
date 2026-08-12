/**
 * 共享业务标签常量 — 跨组件复用的中文标签/选项的唯一事实源。
 *
 * 消除 Admin/DetailPanel/PositionList/GraphFilterPanel 等组件内联重复
 * 的定义与拼写漂移（如 "已发布" vs "已通过" 在不同域的语义差异见各 map 注释）。
 */

// ── 技能熟练度 ──
export const PROFICIENCY_LEVELS = ['精通', '熟悉', '了解'] as const

/** 熟练度 → 数值分（与后端 PROFICIENCY_SCORE 对齐） */
export const PROFICIENCY_MAP: Record<string, number> = {
  精通: 0.9,
  熟悉: 0.65,
  了解: 0.35,
}

// ── 节点分类标签（skill category + Neo4j label 兜底）──
export const CATEGORY_LABELS: Record<string, string> = {
  hard_skill: '硬技能',
  soft_skill: '软技能',
  tool: '工具',
  certificate: '认证',
  project_management: '项目管理',
  design: '设计',
  domain: '领域知识',
  language: '语言',
  certification: '认证',
  methodology: '方法论',
  // Neo4j label fallbacks — 后端修复后不应出现，但做兜底
  Skill: '硬技能',
  Position: '—',
  Tool: '工具',
  Certificate: '认证',
  Industry: '—',
  KnowledgeArea: '领域知识',
  LearningResource: '学习资源',
}

// ── 图谱节点类型标签（Neo4j 6 labels）──
export const NODE_TYPE_LABELS: Record<string, string> = {
  Skill: '技能',
  Tool: '工具',
  Position: '岗位',
  KnowledgeArea: '知识领域',
  Industry: '行业',
  LearningResource: '学习资源',
  Domain: '领域', // legacy alias
  Certificate: '证书',
}

// ── 岗位审核状态（PositionList / ContentReviewPanel）──
export const POSITION_REVIEW_STATUS_LABELS: Record<string, string> = {
  approved: '已发布',
  pending_review: '待审核',
  rejected: '已拒绝',
  draft: '草稿',
}

// ── 图节点审核状态（Admin 图节点管理，语义与岗位审核不同）──
export const NODE_REVIEW_STATUS_LABELS: Record<string, string> = {
  approved: '已通过',
  rejected: '已拒绝',
  pending: '待审核',
}
export const NODE_REVIEW_STATUS_TAGS: Record<string, string> = {
  approved: 'success',
  rejected: 'danger',
  pending: 'warning',
}

// ── 学习进度状态 ──
export const LEARNING_STATUS_LABELS: Record<string, string> = {
  not_started: '未开始',
  in_progress: '学习中',
  mastered: '已掌握',
}

// ── 流水线运行类型 ──
export const RUN_TYPE_LABELS: Record<string, string> = {
  full: '全量',
  incremental: '增量',
}

// ── 演化趋势箭头（rising/stable/declining 键）──
export const TREND_ARROW_LABELS: Record<string, string> = {
  rising: '↑ 上升',
  stable: '→ 平稳',
  declining: '↓ 下降',
}
export const TREND_TYPES: Record<string, string> = {
  rising: 'success',
  stable: 'info',
  declining: 'danger',
}

// ── 数据源名称中文化映射（覆盖爬虫平台、标准库、API 等常见数据源）──
export const SOURCE_NAME_LABELS: Record<string, string> = {
  // 国内招聘平台
  boss: 'BOSS直聘',
  bosszhipin: 'BOSS直聘',
  'BOSS直聘': 'BOSS直聘',
  lagou: '拉勾网',
  '拉勾网': '拉勾网',
  '51job': '前程无忧',
  '51Job': '前程无忧',
  zhaopin: '智联招聘',
  liepin: '猎聘',
  talent: '猎聘',
  // 国际平台
  github: 'GitHub',
  GitHub: 'GitHub',
  indeed: 'Indeed',
  linkedin: 'LinkedIn',
  freelancer: 'Freelancer',
  // 标准库
  esco: 'ESCO 标准库',
  ESCO: 'ESCO 标准库',
  // 其他
  manual: '手动录入',
  import: '数据导入',
  api: 'API 接入',
  test_real_crawl: '测试数据',
  // 内部数据源标识
  jd_extract: 'JD 抽取',
  jd_extraction: 'JD 抽取',
  user_upload: '用户上传',
  // D5: 真实 DB 名称（混合大小写 + (远程) 后缀）→ 中文显示名
  'Boss Zhipin': 'BOSS直聘',
  'Lagou': '拉勾网',
  'ESCO Skills': 'ESCO 职业技能标准',
  'Remotive (远程)': 'Remotive（远程招聘）',
  'Arbeitnow (远程)': 'Arbeitnow（远程招聘）',
  'Jobicy (远程)': 'Jobicy（远程招聘）',
  'WeWorkRemotely (远程)': 'WeWorkRemotely（远程招聘）',
}

// ── 数据源说明（卡片展示：告诉用户这个数据源是什么）──
export const SOURCE_DESCRIPTIONS: Record<string, string> = {
  'Boss Zhipin': '国内主流互联网招聘平台，聚合大量技术岗位 JD',
  'Lagou': '国内互联网招聘平台（拉勾网），覆盖技术/产品/运营岗位',
  'ESCO Skills': '欧盟职业分类标准库 — 结构化技能体系，非爬虫数据源（采集不适用）',
  'Remotive (远程)': '海外远程岗位聚合平台，经 API 抓取',
  'Arbeitnow (远程)': '德国远程岗位聚合平台，经 API 抓取',
  'Jobicy (远程)': '海外远程岗位聚合平台，经 API 抓取',
  'WeWorkRemotely (远程)': '全球远程岗位聚合站，经 RSS 订阅抓取',
}

/** 真实可爬取的平台（有 spider 适配器；ESCO 标准库 / 未配置平台者不可采集） */
export const CRAWLABLE_PLATFORMS = new Set([
  'v2ex', 'remotive', 'arbeitnow', 'jobicy', 'weworkremotely',
  'juejin', 'remoteok',
])

/** 是否支持「立即采集」：有可爬取平台且非标准库 */
export function isCrawlableSource(source: {
  name: string
  config?: Record<string, unknown> | null
}): boolean {
  const platform = source.config?.platform
  return typeof platform === 'string' && platform.length > 0 && CRAWLABLE_PLATFORMS.has(platform)
}

// ── 通用过滤选项 ──
export const ALL_OPTION = '全部'

// ── 分页选项 ──
export const PAGINATION_SIZES_DEFAULT = [10, 20, 50]
export const PAGINATION_SIZES_LARGE = [20, 50, 100, 200]
export const PAGINATION_SIZES_ADMIN = [10, 20, 50, 100]
