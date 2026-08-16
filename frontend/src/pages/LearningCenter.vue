<script setup lang="ts">
/**
 * 学习中心页 — 个性化学习计划管理
 * 顶部：学习计划概览（岗位、总进度、预计完成时间）
 * 左侧：学习路径 DAG 图（技能前置关系 + 当前进度）
 * 右侧：技能进度卡片列表（每个技能的状态、进度、时间、前置）
 * 底部：个性化推荐（基于差距的下一批推荐学习技能）
 */

// 技术说明：引入 Vue 3 组合式 API 核心函数
import { onMounted, computed, ref, watch } from 'vue'
// 技术说明：引入 Vue Router 用于页面导航
import { useRouter } from 'vue-router'
// 技术说明：引入 Element Plus 图标组件
import { Guide, DataAnalysis, Clock, Trophy, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
// 业务说明：主布局组件，提供统一的页面导航和侧边栏
import MainLayout from '@/layouts/MainLayout.vue'
// 业务说明：学习路径可视化组件，展示技能之间的依赖关系图
import LearningPathFlow from '@/components/LearningPathFlow.vue'
// 业务说明：技能进度卡片组件，展示单个技能的学习状态和进度
import SkillProgressCard from '@/components/SkillProgressCard.vue'
// 业务说明：学习中心状态管理 Store，处理学习计划数据、进度更新和推荐逻辑
import { useLearningStore } from '@/stores/learning'
import { useUserStore } from '@/stores/user'
import { ALL_OPTION, LEARNING_STATUS_LABELS } from '@/constants/labels'
import { useMatchStore } from '@/stores/match'
import { asTagType } from '@/utils/element'

// 技术说明：初始化路由实例，用于跳转到匹配诊断页面
const router = useRouter()
// 业务说明：获取学习中心状态管理实例，统一管理学习计划、推荐和数据加载状态
const learningStore = useLearningStore()
const userStore = useUserStore()
const matchStore = useMatchStore()

// 业务说明：当前激活的学习计划，包含岗位信息、技能列表、整体进度等
const currentPlan = computed(() => learningStore.currentPlan)
// 业务说明：基于差距分析生成的个性化技能推荐列表
const recommendations = computed(() => learningStore.recommendations)
// 业务说明：数据加载状态
const isLoading = computed(() => learningStore.loading)

// 业务说明：技能筛选 Tab 状态 + 优先级映射（内联自 useLearningFilters + useLearningPriority）
const activeTab = ref<'all'|'in_progress'|'not_started'>('all')
const filteredSkills = computed(() => {
  const plan = currentPlan.value
  if (!plan) return []
  return activeTab.value === 'all' ? plan.skills : plan.skills.filter((s) => s.status === activeTab.value)
})

const priorityTagMap: Record<string, string> = { high: 'danger', medium: 'warning', low: 'info' }
const priorityLabelMap: Record<string, string> = { high: '高优先', medium: '中优先', low: '低优先' }
function priorityType(p: string) { return priorityTagMap[p] ?? 'info' }
function priorityLabel(p: string) { return priorityLabelMap[p] ?? '低优先' }

// 业务说明：学习进度统计指标（内联自 useLearningMetrics）
const masteredCount = computed(() => currentPlan.value?.skills.filter((s) => s.status === 'mastered').length ?? 0)
const inProgressCount = computed(() => currentPlan.value?.skills.filter((s) => s.status === 'in_progress').length ?? 0)
const remainingHours = computed(() => {
  if (!currentPlan.value) return 0
  return currentPlan.value.skills.filter((s) => s.status !== 'mastered').reduce((sum: number, s) => sum + Math.round(s.estimated_hours * (1 - s.progress_pct / 100)), 0)
})

// 业务说明：用户操作（内联自 useLearningActions）
async function handleUpdateStatus(skill: string, status: string) {
  if (!currentPlan.value) { ElMessage.warning('请先创建学习计划'); return }
  try {
    await learningStore.updateProgress(currentPlan.value.plan_id, skill, status)
    const statusLabel = LEARNING_STATUS_LABELS[status] ?? status
    ElMessage.success(`已更新「${skill}」状态为 ${statusLabel}`)
    if (status === 'mastered') ElMessage.success({ message: '技能已掌握！可前往匹配诊断查看提升效果', duration: 5000 })
  } catch { /* store handles errors */ }
}
// ponytail: 原实现把推荐技能当 position 创建新计划（岗位名=技能名，语义错位），
// 且已有计划时用技能"覆盖"整个计划（破坏性）。
// 正确语义：推荐技能加入现有计划的技能列表；无计划时提示先创建。
async function handleAddToPlan(rec: { skill: string; priority: string }) {
  try {
    if (!currentPlan.value) {
      ElMessage.warning('请先创建学习计划，再将推荐技能加入')
      return
    }
    await learningStore.addSkillToPlan(rec.skill, currentPlan.value.position)
    ElMessage.success(`「${rec.skill}」已加入学习计划「${currentPlan.value.position}」`)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加入计划失败')
  }
}

// FLOW-02-S2: 一键重新匹配 —— 使用更新后的 parsedSkills 对当前岗位重新执行匹配
const rematchLoading = ref(false)
async function handleRematch() {
  if (!currentPlan.value?.position) {
    ElMessage.warning('当前学习计划无目标岗位')
    return
  }
  // FLOW-03: extract skill names from structured parsedSkills
  const skillNames = userStore.parsedSkills.map(s => s.skill)
  if (!skillNames.length) {
    ElMessage.warning('技能列表为空，请先上传简历或标记已掌握的技能')
    return
  }
  rematchLoading.value = true
  try {
    await matchStore.runMatch(currentPlan.value.position, skillNames)
    // 携带匹配结果跳转到 MatchDiagnosis 第4步（差距分析/学习路径）
    router.push({ path: '/match', query: { rematch: '1', position: currentPlan.value.position } })
  } catch {
    ElMessage.error('重新匹配失败，请重试')
  } finally {
    rematchLoading.value = false
  }
}

// 业务说明：是否有已掌握的技能（决定是否显示重新匹配按钮）
const hasMasteredSkills = computed(() =>
  currentPlan.value ? currentPlan.value.skills.some(s => s.status === 'mastered') : false,
)

// 业务说明：页面初始化 —— 恢复 localStorage 计划 + 并行加载推荐
// D-07: 每次打开 LearningCenter 验证 plan_id 有效性
// P1 fix (functional-review 2026-08-13): 先恢复计划，再带 plan_id 拉取
// 个性化推荐（此前并行调用无 plan_id → 恒为市场热门，个性化失效）。
onMounted(async () => {
  try {
    await learningStore.restorePlanFromLocalStorage()
    // QA-FIX: 后端已有学习计划但 localStorage 无记录（换设备/清缓存）时，
    // 从后端同步最近计划，避免页面误显示「暂无学习计划」。
    if (!currentPlan.value) {
      await learningStore.fetchPlans()
    }
    const plan = currentPlan.value
    await learningStore.fetchRecommendations(plan?.plan_id, plan?.position)
  } catch {
    // errors handled by store
  }
})

// P1 fix: 计划变化（创建/切换/清除）后重新拉取个性化推荐。
watch(currentPlan, (plan) => {
  void learningStore.fetchRecommendations(plan?.plan_id, plan?.position)
})
</script>

<template>
  <MainLayout>
    <!-- 业务说明：学习中心页面根容器，包含页面头部、计划概览、主内容区和推荐区域 -->
    <div class="learning-page animate-fade-in">
      <!-- 业务说明：页面头部区域，展示页面标题、功能描述和快捷操作按钮 -->
      <div class="page-header">
        <div>
          <h1 class="page-title">
            学习中心
          </h1>
          <p class="page-desc">
            个性化学习计划管理 — 基于匹配诊断的技能提升路径
          </p>
        </div>
        <div class="header-actions">
          <!-- FLOW-02-S2: 一键重新匹配 —— 使用更新后的技能列表对目标岗位重新执行匹配诊断 -->
          <el-button
            v-if="hasMasteredSkills"
            type="success"
            :icon="RefreshRight"
            size="default"
            :loading="rematchLoading"
            @click="handleRematch"
          >
            重新匹配
          </el-button>
          <!-- 业务说明：快捷入口 —— 跳转到匹配诊断页面生成新的学习计划 -->
          <el-button
            type="primary"
            :icon="Guide"
            size="default"
            @click="router.push('/match')"
          >
            从匹配诊断生成
          </el-button>
        </div>
      </div>

      <!-- 业务说明：学习计划概览卡片 —— 展示当前岗位、整体进度、预计完成时间和关键统计数据 -->
      <!-- 当有活跃学习计划时显示详细概览，无计划时显示空状态引导 -->
      <template v-if="currentPlan">
        <el-card
          class="plan-summary"
          shadow="hover"
        >
          <div class="summary-grid">
            <!-- 业务说明：概览左侧 —— 岗位信息、总进度条和预计完成时间 -->
            <div class="summary-main">
              <div class="summary-position">
                <h2 class="position-name">
                  {{ currentPlan.position }}
                </h2>
                <el-tag
                  effect="plain"
                  size="small"
                >
                  学习计划
                </el-tag>
              </div>
              <div class="progress-row">
                <!-- 业务说明：总进度可视化 —— 根据进度值动态调整颜色（>=80%绿色，>=40%黄色，<40%蓝色） -->
                <el-progress
                  :percentage="currentPlan.overall_progress"
                  :stroke-width="14"
                  :color="currentPlan.overall_progress >= 80 ? 'var(--success)' : currentPlan.overall_progress >= 40 ? 'var(--warning)' : 'var(--primary)'"
                  class="main-progress"
                />
                <span class="progress-label">总进度</span>
              </div>
              <div class="summary-meta">
                <span class="meta-item">
                  <el-icon><Clock /></el-icon>
                  预计完成：{{ currentPlan.estimated_completion }}
                </span>
                <span
                  v-if="currentPlan.updated_at"
                  class="meta-item"
                >
                  最后更新：{{ new Date(currentPlan.updated_at).toLocaleDateString() }}
                </span>
              </div>
            </div>

            <!-- 业务说明：概览右侧 —— 四项关键统计数据展示（已掌握/学习中/未开始/剩余小时） -->
            <div class="summary-stats">
              <div class="stat-card">
                <div class="stat-value">
                  {{ masteredCount }}
                </div>
                <div class="stat-label">
                  已掌握
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-value stat-warn">
                  {{ inProgressCount }}
                </div>
                <div class="stat-label">
                  学习中
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-value stat-info">
                  {{ currentPlan.skills.length - masteredCount - inProgressCount }}
                </div>
                <div class="stat-label">
                  未开始
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-value stat-accent">
                  {{ remainingHours }}
                </div>
                <div class="stat-label">
                  剩余小时
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </template>
      <!-- 业务说明：空状态 —— 当用户尚未创建学习计划时，引导用户前往匹配诊断页面生成计划 -->
      <template v-else>
        <el-card
          class="plan-summary"
          shadow="hover"
        >
          <div class="empty-state-wrapper">
            <p class="empty-main-text">
              暂无学习计划
            </p>
            <p class="empty-hint-text">
              在下方推荐中选择技能创建学习计划，或前往「匹配诊断」基于差距分析生成个性化学习路径
            </p>
            <el-button
              type="primary"
              @click="router.push('/match')"
            >
              从匹配诊断生成
            </el-button>
          </div>
        </el-card>
      </template>

      <!-- 业务说明：主内容区 —— 左右分栏布局，左侧展示学习路径 DAG 图，右侧展示技能进度卡片列表 -->
      <template v-if="currentPlan">
        <el-row
          :gutter="20"
          class="main-content"
        >
          <!-- 业务说明：左侧 —— 学习路径 DAG 可视化图
               以有向无环图形式展示技能之间的前置依赖关系，帮助用户理解学习顺序 -->
          <el-col
            :xs="24"
            :lg="10"
          >
            <el-card
              class="path-card"
              shadow="hover"
            >
              <template #header>
                <div class="card-header-row">
                  <span class="card-title">学习路径图</span>
                  <el-tag
                    size="small"
                    effect="plain"
                    type="info"
                  >
                    DAG
                  </el-tag>
                </div>
              </template>
              <!-- 业务说明：学习路径图组件，接收当前计划的路径数据渲染技能节点和依赖连线 -->
              <LearningPathFlow :path="currentPlan.path" />
            </el-card>
          </el-col>

          <!-- 业务说明：右侧 —— 技能进度卡片列表
               支持按状态筛选（全部/学习中/未开始），每张卡片展示单个技能的详细进度信息 -->
          <el-col
            :xs="24"
            :lg="14"
          >
            <el-card
              class="skills-card"
              shadow="hover"
            >
              <template #header>
                <div class="card-header-row">
                  <span class="card-title">技能进度</span>
                  <!-- 业务说明：分段控制器 —— 切换技能筛选条件，实时过滤显示对应状态的技能 -->
                  <el-segmented
                    v-model="activeTab"
                    :options="[
                      { label: ALL_OPTION, value: 'all' },
                      { label: LEARNING_STATUS_LABELS.in_progress, value: 'in_progress' },
                      { label: LEARNING_STATUS_LABELS.not_started, value: 'not_started' },
                    ]"
                    size="small"
                  />
                </div>
              </template>
              <div
                v-loading="isLoading"
                class="skills-grid"
              >
                <!-- 业务说明：遍历筛选后的技能列表，渲染技能进度卡片
                     每张卡片支持状态更新操作（标记为已掌握/学习中/未开始） -->
                <SkillProgressCard
                  v-for="skill in filteredSkills"
                  :key="skill.skill"
                  :skill="skill"
                  @update-status="handleUpdateStatus"
                />
                <!-- 业务说明：空状态 —— 当筛选结果为空时显示提示信息 -->
                <div
                  v-if="!filteredSkills.length"
                  class="custom-empty"
                >
                  <p class="empty-text">
                    暂无匹配的技能
                  </p>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </template>
      <!-- 业务说明：空状态 —— 主内容区在无学习计划时的占位提示 -->
      <template v-else>
        <el-row
          :gutter="20"
          class="main-content"
        >
          <el-col :span="24">
            <el-card shadow="hover">
              <div class="empty-state-wrapper">
                <p class="empty-main-text">
                  暂无学习计划
                </p>
                <p class="empty-hint-text">
                  请先通过「匹配诊断」创建学习计划，或在下方推荐中选择技能加入计划
                </p>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </template>

      <!-- 业务说明：个性化推荐区域 —— 基于差距分析算法生成下一批推荐学习技能
           展示技能名称、优先级、推荐理由、预计学时和市场需求，支持一键加入计划 -->
      <el-card
        class="recommendations-card"
        shadow="hover"
      >
        <template #header>
          <div class="card-header-row">
            <span class="card-title">
              <el-icon class="mr-1">
                <Trophy />
              </el-icon>
              个性化推荐
            </span>
            <el-tag
              size="small"
              effect="plain"
              type="warning"
            >
              基于差距分析
            </el-tag>
          </div>
        </template>
        <!-- 业务说明：推荐列表 —— 当存在推荐数据时展示网格卡片 -->
        <div
          v-if="recommendations.length"
          class="recommendations-grid"
        >
          <div
            v-for="rec in recommendations"
            :key="rec.skill"
            class="rec-item"
          >
            <div class="rec-top">
              <span class="rec-skill">{{ rec.skill }}</span>
              <!-- 业务说明：优先级标签 —— 高/中/低优先级用不同颜色区分，帮助用户决策学习顺序 -->
              <el-tag
                :type="asTagType(priorityType(rec.priority))"
                size="small"
                effect="plain"
              >
                {{ priorityLabel(rec.priority) }}
              </el-tag>
            </div>
            <!-- 业务说明：推荐理由 —— 解释为什么推荐该技能（如岗位差距、市场需求等） -->
            <p class="rec-reason">
              {{ rec.reason }}
            </p>
            <div class="rec-meta">
              <span class="rec-meta-item">
                <el-icon><Clock /></el-icon>
                {{ rec.estimated_hours }}h
              </span>
              <span
                v-if="rec.market_demand"
                class="rec-meta-item"
              >
                <el-icon><DataAnalysis /></el-icon>
                需求 {{ rec.market_demand }}%
              </span>
            </div>
            <div class="rec-action">
              <!-- 业务说明：加入计划按钮 —— 将推荐技能添加到当前学习计划中，无计划时禁用
                   QA-FIX: 原按钮无计划时文案为「创建计划」但行为仅弹提示，语义误导；
                   改为始终「加入计划」，无计划时禁用并给出引导 tooltip。 -->
              <el-button
                size="small"
                type="primary"
                plain
                :disabled="!currentPlan"
                :title="currentPlan ? '' : '请先创建学习计划（从「匹配诊断」生成）'"
                @click="handleAddToPlan(rec)"
              >
                加入计划
              </el-button>
            </div>
          </div>
        </div>
        <!-- 业务说明：空状态 —— 当无推荐数据时显示引导信息 -->
        <div
          v-else
          class="empty-state-wrapper"
        >
          <p class="empty-main-text">
            暂无推荐
          </p>
          <p class="empty-hint-text">
            创建学习计划后将基于差距分析生成个性化推荐
          </p>
        </div>
      </el-card>
    </div>
  </MainLayout>
</template>

<style scoped>
.learning-page {
  max-width: 1200px;
  margin: 0 auto;
}

/* Page Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-6);
}
.page-title {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}
.page-desc {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
  line-height: var(--leading-relaxed);
}
.header-actions {
  flex-shrink: 0;
}

/* Plan Summary */
.plan-summary {
  margin-bottom: var(--space-6);
  position: relative;
  overflow: hidden;
}
.plan-summary::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary), var(--chart-2), var(--chart-3));
  opacity: 0.8;
}
.summary-grid {
  display: flex;
  gap: var(--space-6);
  align-items: flex-start;
}
.summary-main {
  flex: 1;
  min-width: 0;
}
.summary-position {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.position-name {
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}
.progress-row {
  margin-bottom: var(--space-3);
}
.main-progress {
  width: 100%;
}
.progress-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  display: block;
  margin-top: var(--space-1);
}
.summary-meta {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
}
.summary-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
  flex-shrink: 0;
}
.stat-card {
  padding: var(--space-3) var(--space-4);
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 3%, var(--card)), var(--card));
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  text-align: center;
  min-width: 90px;
}
.stat-value {
  font-size: var(--font-size-2xl);
  font-weight: 800;
  color: var(--success);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.03em;
}
.stat-warn {
  color: var(--warning);
}
.stat-info {
  color: var(--muted-foreground);
}
.stat-accent {
  color: var(--primary);
}
.stat-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  margin-top: var(--space-1);
}

/* Main Content */
.main-content {
  margin-bottom: var(--space-6);
}

/* Cards */
.path-card,
.skills-card,
.recommendations-card {
  margin-bottom: var(--space-5);
}
.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.card-title {
  font-weight: 700;
  font-size: var(--font-size-base);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

/* Skills Grid */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
  min-height: 200px;
}

/* Recommendations */
.recommendations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-4);
}
.rec-item {
  padding: var(--space-4);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}
.rec-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--warning);
  border-radius: 0 2px 2px 0;
  opacity: 0;
  transition: opacity var(--duration-fast);
}
.rec-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: color-mix(in srgb, var(--warning) 30%, var(--border));
}
.rec-item:hover::before {
  opacity: 1;
}
.rec-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}
.rec-skill {
  font-size: var(--font-size-base);
  font-weight: 700;
  color: var(--foreground);
  letter-spacing: var(--tracking-tight);
}
.rec-reason {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  line-height: var(--leading-relaxed);
  margin: 0 0 var(--space-3);
}
.rec-meta {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-3);
}
.rec-meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
}
.rec-action {
  display: flex;
  justify-content: flex-end;
}

.mr-1 {
  margin-right: var(--space-1);
}

/* Custom empty */
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) var(--space-6);
  text-align: center;
  grid-column: 1 / -1;
}
.empty-text {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
}

/* Empty state wrapper */
.empty-state-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) var(--space-6);
  text-align: center;
  gap: var(--space-3);
}
.empty-main-text {
  font-size: var(--font-size-lg);
  font-weight: 700;
  color: var(--foreground);
  margin: 0;
}
.empty-hint-text {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: 0;
}

/* Responsive */
@media (max-width: 1024px) {
  .summary-grid {
    flex-direction: column;
  }
  .summary-stats {
    grid-template-columns: repeat(4, 1fr);
  }
}
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: var(--space-3);
  }
  .summary-stats {
    grid-template-columns: repeat(2, 1fr);
  }
  .skills-grid {
    grid-template-columns: 1fr;
  }
  .recommendations-grid {
    grid-template-columns: 1fr;
  }
}
</style>
