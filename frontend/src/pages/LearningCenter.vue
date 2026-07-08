<script setup lang="ts">
/**
 * 学习中心页 — 个性化学习计划管理
 * 顶部：学习计划概览（岗位、总进度、预计完成时间）
 * 左侧：学习路径 DAG 图（技能前置关系 + 当前进度）
 * 右侧：技能进度卡片列表（每个技能的状态、进度、时间、前置）
 * 底部：个性化推荐（基于差距的下一批推荐学习技能）
 */

// 技术说明：引入 Vue 3 组合式 API 核心函数
import { ref, onMounted, computed } from 'vue'
// 技术说明：引入 Vue Router 用于页面导航
import { useRouter } from 'vue-router'
// 技术说明：引入 Element Plus 消息提示组件
import { ElMessage, ElMessageBox } from 'element-plus'
// 技术说明：引入 Element Plus 图标组件
import { Guide, DataAnalysis, Clock, Trophy } from '@element-plus/icons-vue'
// 业务说明：主布局组件，提供统一的页面导航和侧边栏
import MainLayout from '@/layouts/MainLayout.vue'
// 业务说明：学习路径可视化组件，展示技能之间的依赖关系图
import LearningPathFlow from '@/components/LearningPathFlow.vue'
// 业务说明：技能进度卡片组件，展示单个技能的学习状态和进度
import SkillProgressCard from '@/components/SkillProgressCard.vue'
// 业务说明：学习中心状态管理 Store，处理学习计划数据、进度更新和推荐逻辑
import { useLearningStore } from '@/stores/learning'
// 技术说明：引入 SkillProgress 类型定义
import type { SkillProgress } from '@/stores/learning'
// 业务说明：拆分到独立 composable 的指标计算与优先级映射
import { useLearningMetrics } from '@/composables/useLearningMetrics'
import { priorityType, priorityLabel } from '@/composables/useLearningPriority'

// 技术说明：初始化路由实例，用于跳转到匹配诊断页面
const router = useRouter()
// 业务说明：获取学习中心状态管理实例，统一管理学习计划、推荐和数据加载状态
const learningStore = useLearningStore()

// 业务说明：当前选中的技能筛选标签，控制右侧技能列表的显示范围
// 可选值：'all'(全部)、'in_progress'(学习中)、'not_started'(未开始)
const activeTab = ref('all')

// 业务说明：根据当前选中的标签筛选技能列表
// 当用户切换标签时，实时过滤显示对应状态的技能卡片
const filteredSkills = computed<SkillProgress[]>(() => {
  if (!currentPlan.value) return []
  if (activeTab.value === 'all') return currentPlan.value.skills
  return currentPlan.value.skills.filter(s => s.status === activeTab.value)
})

// 业务说明：当前激活的学习计划，包含岗位信息、技能列表、整体进度等
// 从 Store 中获取，支持响应式更新
const currentPlan = computed(() => learningStore.currentPlan)
// 业务说明：基于差距分析生成的个性化技能推荐列表
const recommendations = computed(() => learningStore.recommendations)
// 业务说明：数据加载状态，控制骨架屏和加载动画的显示
const isLoading = computed(() => learningStore.loading)

// 业务说明：学习进度统计指标（已掌握/学习中/剩余学时；总学时在 composable 内部保留)
const { masteredCount, inProgressCount, remainingHours } = useLearningMetrics(currentPlan)

// 业务说明：更新技能学习状态
// 用户点击技能卡片上的状态按钮时触发，将技能标记为已掌握/学习中/未开始
// 参数 skill: 技能名称，status: 目标状态
async function handleUpdateStatus(skill: string, status: string) {
  if (!currentPlan.value) {
    ElMessage.warning('请先创建学习计划')
    return
  }
  try {
    await learningStore.updateProgress(currentPlan.value.plan_id, skill, status)
    ElMessage.success(`已更新「${skill}」状态为 ${status === 'mastered' ? '已掌握' : status === 'in_progress' ? '学习中' : '未开始'}`)
  } catch {
    // error handled by store
  }
}

// 业务说明：将推荐技能加入当前学习计划（或创建新计划）
// D-08: 单计划模式；已有计划时覆盖前确认
// D-09: "加入计划"调用 POST /learning/plan；plan_id 写入 localStorage (D-06)
async function handleAddToPlan(rec: { skill: string; priority: string }) {
  try {
    if (currentPlan.value) {
      await ElMessageBox.confirm(
        `已有学习计划「${currentPlan.value.position}」，是否用「${rec.skill}」覆盖？`,
        '覆盖学习计划',
        { confirmButtonText: '确认覆盖', cancelButtonText: '取消', type: 'warning' }
      )
      await learningStore.createPlan({
        position: rec.skill,
        skills: [{ skill: rec.skill, importance: 'required', gap_level: '完全缺失' }],
      })
      ElMessage.success('已创建新学习计划')
    } else {
      await learningStore.createPlan({
        position: rec.skill,
        skills: [{ skill: rec.skill, importance: 'required', gap_level: '完全缺失' }],
      })
      ElMessage.success(`「${rec.skill}」已加入学习计划`)
    }
  } catch (e: unknown) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e instanceof Error ? e.message : '加入计划失败')
  }
}

// 业务说明：页面初始化 —— 恢复 localStorage 计划 + 并行加载推荐
// D-07: 每次打开 LearningCenter 验证 plan_id 有效性
onMounted(async () => {
  try {
    await Promise.all([
      learningStore.restorePlanFromLocalStorage(),
      learningStore.fetchRecommendations(),
    ])
  } catch {
    // errors handled by store
  }
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
                      { label: '全部', value: 'all' },
                      { label: '学习中', value: 'in_progress' },
                      { label: '未开始', value: 'not_started' },
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
                :type="priorityType(rec.priority) as any"
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
              <!-- 业务说明：加入计划按钮 —— 将推荐技能添加到当前学习计划中，无计划时禁用 -->
              <el-button
                size="small"
                type="primary"
                plain
                @click="handleAddToPlan(rec)"
              >
                {{ currentPlan ? '加入计划' : '创建计划' }}
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
