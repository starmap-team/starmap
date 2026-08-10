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
}

// ── 通用过滤选项 ──
export const ALL_OPTION = '全部'

// ── 分页选项 ──
export const PAGINATION_SIZES_DEFAULT = [10, 20, 50]
export const PAGINATION_SIZES_LARGE = [20, 50, 100, 200]
export const PAGINATION_SIZES_ADMIN = [10, 20, 50, 100]
