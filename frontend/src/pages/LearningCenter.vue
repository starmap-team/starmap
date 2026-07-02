<script setup lang="ts">
/**
 * 学习中心页 — 个性化学习计划管理
 * 顶部：学习计划概览（岗位、总进度、预计完成时间）
 * 左侧：学习路径 DAG 图（技能前置关系 + 当前进度）
 * 右侧：技能进度卡片列表（每个技能的状态、进度、时间、前置）
 * 底部：个性化推荐（基于差距的下一批推荐学习技能）
 */
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Guide, DataAnalysis, Clock, Trophy } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import LearningPathFlow from '@/components/LearningPathFlow.vue'
import SkillProgressCard from '@/components/SkillProgressCard.vue'
import { useLearningStore } from '@/stores/learning'
import type { LearningPlan, SkillProgress } from '@/stores/learning'

const router = useRouter()
const learningStore = useLearningStore()

const activeTab = ref('all')

// ── Filtered skills based on activeTab ──
const filteredSkills = computed<SkillProgress[]>(() => {
  if (activeTab.value === 'all') return currentPlan.value.skills
  return currentPlan.value.skills.filter(s => s.status === activeTab.value)
})

// ── Demo data for initial display ──
const demoPlan: LearningPlan = {
  plan_id: 'demo-plan-1',
  position: '高级前端工程师',
  overall_progress: 35,
  estimated_completion: '约 3 个月',
  skills: [
    { skill: 'TypeScript', status: 'mastered', progress_pct: 100, estimated_hours: 0, prerequisites: ['JavaScript'], current_level: 4, target_level: 4 },
    { skill: 'Vue 3', status: 'mastered', progress_pct: 100, estimated_hours: 0, prerequisites: ['TypeScript'], current_level: 4, target_level: 4 },
    { skill: 'React', status: 'in_progress', progress_pct: 60, estimated_hours: 40, prerequisites: ['JavaScript', 'TypeScript'], current_level: 3, target_level: 4 },
    { skill: 'Node.js', status: 'in_progress', progress_pct: 45, estimated_hours: 60, prerequisites: ['JavaScript'], current_level: 2, target_level: 4 },
    { skill: 'GraphQL', status: 'not_started', progress_pct: 0, estimated_hours: 30, prerequisites: ['Node.js'], current_level: 1, target_level: 3 },
    { skill: 'Docker', status: 'not_started', progress_pct: 0, estimated_hours: 25, prerequisites: ['Node.js'], current_level: 0, target_level: 3 },
    { skill: 'CI/CD', status: 'not_started', progress_pct: 0, estimated_hours: 20, prerequisites: ['Docker'], current_level: 0, target_level: 3 },
    { skill: '微前端', status: 'not_started', progress_pct: 0, estimated_hours: 35, prerequisites: ['Vue 3', 'React'], current_level: 0, target_level: 3 },
  ],
  path: [
    { skill: 'JavaScript', status: 'mastered', prerequisites: [], estimated_hours: 0, progress_pct: 100 },
    { skill: 'TypeScript', status: 'mastered', prerequisites: ['JavaScript'], estimated_hours: 0, progress_pct: 100 },
    { skill: 'Vue 3', status: 'mastered', prerequisites: ['TypeScript'], estimated_hours: 0, progress_pct: 100 },
    { skill: 'React', status: 'in_progress', prerequisites: ['TypeScript'], estimated_hours: 40, progress_pct: 60 },
    { skill: 'Node.js', status: 'in_progress', prerequisites: ['JavaScript'], estimated_hours: 60, progress_pct: 45 },
    { skill: 'GraphQL', status: 'not_started', prerequisites: ['Node.js'], estimated_hours: 30, progress_pct: 0 },
    { skill: 'Docker', status: 'not_started', prerequisites: ['Node.js'], estimated_hours: 25, progress_pct: 0 },
    { skill: 'CI/CD', status: 'not_started', prerequisites: ['Docker'], estimated_hours: 20, progress_pct: 0 },
    { skill: '微前端', status: 'not_started', prerequisites: ['Vue 3', 'React'], estimated_hours: 35, progress_pct: 0 },
  ],
  created_at: '2026-06-01T10:00:00Z',
  updated_at: '2026-06-25T14:30:00Z',
}

const demoRecommendations = [
  { skill: 'React', reason: '岗位必备技能，你已有基础，建议优先提升', priority: 'high' as const, estimated_hours: 40, market_demand: 92 },
  { skill: 'GraphQL', reason: '市场需求上升，与现有 Node.js 技能互补', priority: 'high' as const, estimated_hours: 30, market_demand: 78 },
  { skill: 'Docker', reason: '现代开发必备，DevOps 基础', priority: 'medium' as const, estimated_hours: 25, market_demand: 85 },
  { skill: 'CI/CD', reason: '工程化能力体现，建议在 Docker 后学习', priority: 'medium' as const, estimated_hours: 20, market_demand: 70 },
  { skill: '微前端', reason: '大型项目架构能力，加分项', priority: 'low' as const, estimated_hours: 35, market_demand: 55 },
]

// Use real plan if available, otherwise demo
const currentPlan = computed(() => learningStore.currentPlan ?? demoPlan)
const recommendations = computed(() => learningStore.recommendations.length ? learningStore.recommendations : demoRecommendations)
const isLoading = computed(() => learningStore.loading)

// Stats
const masteredCount = computed(() => currentPlan.value.skills.filter(s => s.status === 'mastered').length)
const inProgressCount = computed(() => currentPlan.value.skills.filter(s => s.status === 'in_progress').length)
const totalHours = computed(() => currentPlan.value.skills.reduce((sum, s) => sum + s.estimated_hours, 0))
const remainingHours = computed(() => {
  return currentPlan.value.skills
    .filter(s => s.status !== 'mastered')
    .reduce((sum, s) => sum + Math.round(s.estimated_hours * (1 - s.progress_pct / 100)), 0)
})

// Priority tag type
function priorityType(p: string): string {
  return p === 'high' ? 'danger' : p === 'medium' ? 'warning' : 'info'
}
function priorityLabel(p: string): string {
  return p === 'high' ? '高优先' : p === 'medium' ? '中优先' : '低优先'
}

async function handleUpdateStatus(skill: string, status: string) {
  try {
    await learningStore.updateProgress(currentPlan.value.plan_id, skill, status)
    ElMessage.success(`已更新「${skill}」状态为 ${status === 'mastered' ? '已掌握' : status === 'in_progress' ? '学习中' : '未开始'}`)
  } catch {
    // error handled by store
  }
}

onMounted(async () => {
  try {
    await learningStore.fetchRecommendations()
  } catch {
    // use demo data
  }
})
</script>

<template>
  <MainLayout>
    <div class="learning-page animate-fade-in">
      <!-- Page header -->
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

      <!-- Plan Summary (Top) -->
      <el-card
        class="plan-summary"
        shadow="hover"
      >
        <div class="summary-grid">
          <!-- Position & Progress -->
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

          <!-- Stats -->
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

      <!-- Main Content: Left (Path) + Right (Cards) -->
      <el-row
        :gutter="20"
        class="main-content"
      >
        <!-- Left: Learning Path DAG -->
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
            <LearningPathFlow :path="currentPlan.path" />
          </el-card>
        </el-col>

        <!-- Right: Skill Progress Cards -->
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
              <SkillProgressCard
                v-for="skill in filteredSkills"
                :key="skill.skill"
                :skill="skill"
                @update-status="handleUpdateStatus"
              />
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

      <!-- Recommendations (Bottom) -->
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
        <div class="recommendations-grid">
          <div
            v-for="rec in recommendations"
            :key="rec.skill"
            class="rec-item"
          >
            <div class="rec-top">
              <span class="rec-skill">{{ rec.skill }}</span>
              <el-tag
                :type="priorityType(rec.priority) as any"
                size="small"
                effect="plain"
              >
                {{ priorityLabel(rec.priority) }}
              </el-tag>
            </div>
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
              <el-button
                size="small"
                type="primary"
                plain
              >
                加入计划
              </el-button>
            </div>
          </div>
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
