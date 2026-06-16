<script setup lang="ts">
/**
 * 匹配诊断页 — R6 曾洋涛
 * 5 步：上传简历 → 选岗位 → 雷达图 → 差距报告 → 学习路径
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Edit, Search, DataAnalysis, Document, ChatDotSquare, Guide, ArrowLeft, Check, RefreshRight, Plus } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import ResumeUpload from '@/components/ResumeUpload.vue'
import PositionSearch from '@/components/PositionSearch.vue'
import SkillRadar from '@/components/SkillRadar.vue'
import { useUserStore } from '@/stores/user'
import { useResumeStore } from '@/stores/resume'
import { useMatchStore } from '@/stores/match'
import type { RadarItem } from '@/components/SkillRadar.vue'

const userStore = useUserStore()
const resumeStore = useResumeStore()
const matchStore = useMatchStore()

const step = ref(0)
const targetPositionId = ref('')
const targetPositionName = ref('')
const radarData = ref<RadarItem[]>([])
const radarLoading = ref(false)

// 技能熟练度 → 数值映射（用于雷达图）
const PROFICIENCY_MAP: Record<string, number> = { '精通': 0.9, '熟悉': 0.65, '了解': 0.35 }

const stepTitles = ['上传简历', '选择目标岗位', '技能雷达对比', '差距分析报告', '学习路径规划']

// ── Step 0: 上传简历 ──
async function handleUpload(file: File) {
  await resumeStore.parseResume(file)
  userStore.setResume(file.name, resumeStore.result?.required_skills.map(s => s.skill) ?? [])
  ElMessage.success('简历解析完成，识别 ' + userStore.parsedSkills.length + ' 项技能')
  step.value = 1
}

// 手动输入技能（标签式）
const skillInput = ref('')
const manualSkills = ref<string[]>([])
const showManualInput = ref(false)

function addManualSkill() {
  const val = skillInput.value.trim()
  if (!val) return
  if (manualSkills.value.includes(val)) {
    ElMessage.warning('该技能已添加')
    return
  }
  manualSkills.value.push(val)
  skillInput.value = ''
}

function removeManualSkill(skill: string) {
  manualSkills.value = manualSkills.value.filter(s => s !== skill)
}

function confirmManualSkills() {
  if (!manualSkills.value.length) {
    ElMessage.warning('请至少添加一个技能')
    return
  }
  userStore.parsedSkills = [...manualSkills.value]
  ElMessage.success('已录入 ' + manualSkills.value.length + ' 项技能')
  step.value = 1
}

// ── Step 1: 选岗位 ──
async function handlePositionSelect(pos: { position_id: string; name: string }) {
  targetPositionId.value = pos.position_id
  targetPositionName.value = pos.name
  radarLoading.value = true
  try {
    // 契约: GET /graph/position/{position_id}/skills
    const resp = await fetch(`/api/v1/graph/position/${encodeURIComponent(pos.position_id)}/skills`)
    const data = await resp.json()
    // 契约 SkillNode[] → 雷达图 RadarItem[]
    const skills = data.skills ?? []
    radarData.value = skills.map((s: any) => ({
      skill: s.name,
      required: PROFICIENCY_MAP[s.proficiency] ?? 0.5,
      user: 0, // 用户水平从简历抽取结果填入
    }))
    // 填入用户技能水平
    if (resumeStore.result?.required_skills) {
      const userSkills = new Map(resumeStore.result.required_skills.map((s: any) => [s.skill, PROFICIENCY_MAP[s.proficiency] ?? 0.5]))
      radarData.value = radarData.value.map(item => ({
        ...item,
        user: userSkills.get(item.skill) ?? 0,
      }))
    }
    step.value = 2
  } finally {
    radarLoading.value = false
  }
}

// ── Step 2: 开始诊断 ──
async function handleStartDiagnosis() {
  const skills = userStore.parsedSkills.length
    ? userStore.parsedSkills
    : resumeStore.result?.required_skills.map(s => s.skill) ?? []
  await matchStore.runMatch(targetPositionName.value, skills)
  step.value = 3
}

// ── Step 3: 差距排序 ──
const sortedGaps = computed(() => {
  if (!matchStore.result?.skill_gap_detail) return []
  const gaps = [...matchStore.result.skill_gap_detail]
  const order = { '完全缺失': 0, '部分掌握': 1, '已掌握': 2 }
  gaps.sort((a, b) => {
    if (a.importance !== b.importance) return a.importance === 'required' ? -1 : 1
    return (order[a.gap_level as keyof typeof order] ?? 0) - (order[b.gap_level as keyof typeof order] ?? 0)
  })
  return gaps
})

// 技能掌握程度 → 进度条数值
function gapToProgress(level: string) {
  if (level === '已掌握') return 100
  if (level === '部分掌握') return 45
  return 8
}
function gapToColor(level: string) {
  if (level === '已掌握') return '#67c23a'
  if (level === '部分掌握') return '#e6a23c'
  return '#f56c6c'
}

// ── 重置 ──
function handleReset() {
  step.value = 0
  targetPositionId.value = ''
  targetPositionName.value = ''
  radarData.value = []
  manualSkills.value = []
  skillInput.value = ''
  showManualInput.value = false
  matchStore.result = null
  userStore.clearResume()
}
</script>

<template>
  <MainLayout>
    <div class="match-page">
      <div class="page-header">
        <h2>匹配诊断</h2>
        <p class="page-desc">
          上传简历或输入技能，智能诊断与目标岗位的匹配度
        </p>
      </div>

      <!-- 步骤条 -->
      <div class="steps-wrapper">
        <el-steps
          :active="step"
          finish-status="success"
          align-center
        >
          <el-step
            v-for="(title, idx) in stepTitles"
            :key="idx"
          >
            <template #title>
              <span class="step-title">{{ idx + 1 }}. {{ title }}</span>
            </template>
          </el-step>
        </el-steps>
      </div>

      <!-- 步骤内容区（带动画过渡） -->
      <transition
        name="step-fade"
        mode="out-in"
      >
        <div
          :key="step"
          class="step-content"
        >
          <!-- ═══ Step 0 ═══ -->
          <template v-if="step === 0">
            <el-card
              shadow="never"
              class="step-card"
            >
              <template #header>
                <div class="card-header">
                  <el-icon size="20">
                    <Upload />
                  </el-icon>
                  <span>第1步：上传简历</span>
                </div>
              </template>

              <ResumeUpload @upload="handleUpload" />

              <el-divider>
                <el-icon><Edit /></el-icon>
                <span style="margin-left: 4px">或手动输入技能</span>
              </el-divider>

              <div
                v-if="!showManualInput"
                style="text-align: center"
              >
                <el-button
                  type="primary"
                  plain
                  @click="showManualInput = true"
                >
                  跳过上传，手动输入技能
                </el-button>
              </div>

              <div
                v-else
                class="manual-skills"
              >
                <div class="skill-input-row">
                  <el-input
                    v-model="skillInput"
                    placeholder="输入技能名，按回车添加"
                    style="flex: 1; min-width: 220px"
                    @keyup.enter="addManualSkill"
                  >
                    <template #append>
                      <el-button
                        :icon="Plus"
                        @click="addManualSkill"
                      >
                        添加
                      </el-button>
                    </template>
                  </el-input>
                </div>

                <!-- 已添加技能标签 -->
                <div
                  v-if="manualSkills.length"
                  class="skill-tags"
                >
                  <el-tag
                    v-for="s in manualSkills"
                    :key="s"
                    closable
                    :disable-transitions="false"
                    size="large"
                    style="margin: 4px"
                    @close="removeManualSkill(s)"
                  >
                    {{ s }}
                  </el-tag>
                </div>
                <div
                  v-else
                  class="empty-hint"
                >
                  请在上方输入技能并点击"添加"
                </div>

                <div
                  v-if="manualSkills.length"
                  style="margin-top: 16px; display: flex; gap: 12px"
                >
                  <el-button
                    type="primary"
                    @click="confirmManualSkills"
                  >
                    确认（{{ manualSkills.length }} 项技能）并进入下一步
                  </el-button>
                  <el-button @click="showManualInput = false; manualSkills = []">
                    取消
                  </el-button>
                </div>
              </div>
            </el-card>
          </template>

          <!-- ═══ Step 1 ═══ -->
          <template v-else-if="step === 1">
            <el-card
              shadow="never"
              class="step-card"
            >
              <template #header>
                <div class="card-header">
                  <el-icon size="20">
                    <Search />
                  </el-icon>
                  <span>第2步：选择目标岗位</span>
                </div>
              </template>

              <div
                v-if="userStore.parsedSkills.length"
                class="my-skills"
              >
                <div class="skills-label">
                  我的技能：
                </div>
                <div class="skills-list">
                  <el-tag
                    v-for="s in userStore.parsedSkills"
                    :key="s"
                    size="large"
                    effect="plain"
                    style="margin: 3px"
                  >
                    {{ s }}
                  </el-tag>
                </div>
              </div>

              <el-divider />

              <label class="field-label">搜索目标岗位</label>
              <PositionSearch @select="handlePositionSelect" />

              <div style="margin-top: 20px">
                <el-button
                  :icon="ArrowLeft"
                  @click="step = 0"
                >
                  返回上一步
                </el-button>
              </div>
            </el-card>

            <el-card
              v-if="radarLoading"
              style="margin-top: 16px"
              shadow="never"
            >
              <el-skeleton
                :rows="4"
                animated
              />
            </el-card>
          </template>

          <!-- ═══ Step 2 ═══ -->
          <template v-else-if="step === 2">
            <el-card
              shadow="never"
              class="step-card"
            >
              <template #header>
                <div class="card-header">
                  <el-icon size="20">
                    <DataAnalysis />
                  </el-icon>
                  <span>第3步：技能雷达对比 — {{ targetPositionName }}</span>
                </div>
              </template>

              <SkillRadar
                :data="radarData"
                :position-name="targetPositionName"
              />

              <el-alert
                title="如何读图？"
                type="info"
                :closable="false"
                show-icon
                style="margin-top: 16px"
              >
                <template #default>
                  <p style="margin: 0; line-height: 1.8">
                    <span
                      class="legend-dot"
                      style="background: #f56c6c"
                    /> <strong>红色</strong> = 岗位要求水平 &emsp;
                    <span
                      class="legend-dot"
                      style="background: #409eff"
                    /> <strong>蓝色</strong> = 您当前水平<br>
                    蓝色越接近红色，匹配度越高；大面积红色裸露 = 需要重点提升。
                  </p>
                </template>
              </el-alert>

              <div class="step-actions">
                <el-button
                  type="primary"
                  size="large"
                  :loading="matchStore.loading"
                  :icon="Check"
                  @click="handleStartDiagnosis"
                >
                  开始智能诊断
                </el-button>
                <el-button
                  size="large"
                  :icon="ArrowLeft"
                  @click="step = 1"
                >
                  返回选岗位
                </el-button>
              </div>
            </el-card>
          </template>

          <!-- ═══ Step 3 ═══ -->
          <template v-else-if="step === 3 && matchStore.result">
            <!-- 匹配分数 -->
            <el-card
              shadow="never"
              class="score-card"
            >
              <div class="score-circle">
                <el-progress
                  type="dashboard"
                  :percentage="Math.round(matchStore.result.match_score * 100)"
                  :color="matchStore.result.match_score >= 0.7 ? '#67c23a' : matchStore.result.match_score >= 0.5 ? '#e6a23c' : '#f56c6c'"
                  :stroke-width="14"
                  :width="180"
                >
                  <template #default="{ percentage }">
                    <span class="score-value">{{ percentage }}%</span>
                  </template>
                </el-progress>
                <div class="score-label">
                  综合匹配度
                </div>
                <div class="score-target">
                  <el-tag
                    type="primary"
                    size="large"
                  >
                    {{ matchStore.result.target_position }}
                  </el-tag>
                </div>
              </div>
            </el-card>

            <!-- 技能三栏 -->
            <el-row
              :gutter="16"
              style="margin-top: 16px"
            >
              <el-col
                :md="8"
                :sm="24"
              >
                <el-card
                  shadow="hover"
                  class="skill-card matched"
                >
                  <template #header>
                    <span class="skill-card-title">✅ 已掌握（{{ matchStore.result.matched_skills.length }}）</span>
                  </template>
                  <div
                    v-if="matchStore.result.matched_skills.length"
                    class="skill-tags-mini"
                  >
                    <el-tag
                      v-for="s in matchStore.result.matched_skills"
                      :key="s"
                      type="success"
                      size="large"
                      effect="plain"
                      style="margin: 3px"
                    >
                      {{ s }}
                    </el-tag>
                  </div>
                  <el-empty
                    v-else
                    description="暂无"
                    :image-size="60"
                  />
                </el-card>
              </el-col>
              <el-col
                :md="8"
                :sm="24"
              >
                <el-card
                  shadow="hover"
                  class="skill-card missing-req"
                >
                  <template #header>
                    <span class="skill-card-title">🔴 缺失必备（{{ (matchStore.result.missing_required ?? []).length }}）</span>
                  </template>
                  <div
                    v-if="(matchStore.result.missing_required ?? []).length"
                    class="skill-tags-mini"
                  >
                    <el-tag
                      v-for="s in (matchStore.result.missing_required ?? [])"
                      :key="s"
                      type="danger"
                      size="large"
                      effect="plain"
                      style="margin: 3px"
                    >
                      {{ s }}
                    </el-tag>
                  </div>
                  <el-empty
                    v-else
                    description="全部满足！"
                    :image-size="60"
                  />
                </el-card>
              </el-col>
              <el-col
                :md="8"
                :sm="24"
              >
                <el-card
                  shadow="hover"
                  class="skill-card missing-bonus"
                >
                  <template #header>
                    <span class="skill-card-title">🟡 缺失加分（{{ (matchStore.result.missing_bonus ?? []).length }}）</span>
                  </template>
                  <div
                    v-if="(matchStore.result.missing_bonus ?? []).length"
                    class="skill-tags-mini"
                  >
                    <el-tag
                      v-for="s in (matchStore.result.missing_bonus ?? [])"
                      :key="s"
                      type="warning"
                      size="large"
                      effect="plain"
                      style="margin: 3px"
                    >
                      {{ s }}
                    </el-tag>
                  </div>
                  <el-empty
                    v-else
                    description="暂无"
                    :image-size="60"
                  />
                </el-card>
              </el-col>
            </el-row>

            <!-- 差距报告表格 -->
            <el-card
              shadow="never"
              class="step-card"
              style="margin-top: 16px"
            >
              <template #header>
                <div class="card-header">
                  <el-icon size="20">
                    <Document />
                  </el-icon>
                  <span>第4步：差距分析报告（按重要度排序）</span>
                </div>
              </template>

              <el-table
                :data="sortedGaps"
                stripe
                style="width: 100%"
              >
                <el-table-column
                  label="优先级"
                  width="85"
                  align="center"
                >
                  <template #default="{ row }">
                    <el-tag
                      :type="row.importance === 'required' ? 'danger' : 'warning'"
                      size="small"
                      effect="dark"
                    >
                      {{ row.importance === 'required' ? '必备' : '加分' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column
                  prop="skill"
                  label="技能"
                  width="150"
                />
                <el-table-column
                  label="掌握程度"
                  width="180"
                >
                  <template #default="{ row }">
                    <div class="gap-progress">
                      <el-progress
                        :percentage="gapToProgress(row.gap_level)"
                        :color="gapToColor(row.gap_level)"
                        :stroke-width="14"
                        :text-inside="true"
                      >
                        <span>{{ row.gap_level }}</span>
                      </el-progress>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column
                  prop="learning_path"
                  label="推荐学习路径"
                  min-width="280"
                >
                  <template #default="{ row }">
                    <div class="learning-path-preview">
                      {{ row.learning_path }}
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>

            <!-- 总体评估 -->
            <el-card
              shadow="hover"
              style="margin-top: 16px"
            >
              <template #header>
                <div class="card-header">
                  <el-icon size="20">
                    <ChatDotSquare />
                  </el-icon>
                  <span>总体评估</span>
                </div>
              </template>
              <p class="assessment-text">
                {{ matchStore.result.overall_assessment }}
              </p>
              <el-alert
                :title="'⏱ 预估学习时长：' + matchStore.result.estimated_learning_time"
                type="warning"
                :closable="false"
                show-icon
                style="margin-top: 12px"
              />
            </el-card>

            <div class="step-actions">
              <el-button
                type="primary"
                size="large"
                :icon="Guide"
                @click="step = 4"
              >
                查看学习路径规划
              </el-button>
              <el-button
                size="large"
                :icon="RefreshRight"
                @click="handleReset"
              >
                重新诊断
              </el-button>
            </div>
          </template>

          <!-- ═══ Step 4 ═══ -->
          <template v-else-if="step === 4 && matchStore.result">
            <el-card
              shadow="never"
              class="step-card"
            >
              <template #header>
                <div class="card-header">
                  <el-icon size="20">
                    <Guide />
                  </el-icon>
                  <span>第5步：学习路径规划</span>
                </div>
              </template>

              <el-alert
                type="info"
                :closable="false"
                show-icon
                style="margin-bottom: 24px"
              >
                <template #title>
                  预估总学习时长：<strong>{{ matchStore.result.estimated_learning_time }}</strong>
                </template>
              </el-alert>

              <div class="learning-paths">
                <el-card
                  v-for="gap in sortedGaps"
                  :key="gap.skill"
                  shadow="hover"
                  class="learning-card"
                  :style="{ borderLeft: `4px solid ${gap.importance === 'required' ? '#f56c6c' : '#e6a23c'}` }"
                >
                  <template #header>
                    <div class="learning-header">
                      <div>
                        <el-tag
                          :type="gap.importance === 'required' ? 'danger' : 'warning'"
                          size="small"
                          effect="dark"
                        >
                          {{ gap.importance === 'required' ? '必备' : '加分' }}
                        </el-tag>
                        <strong style="margin-left: 8px; font-size: 16px">{{ gap.skill }}</strong>
                        <el-tag
                          :type="gap.gap_level === '已掌握' ? 'success' : gap.gap_level === '部分掌握' ? 'warning' : 'danger'"
                          size="small"
                          style="margin-left: 8px"
                        >
                          {{ gap.gap_level }}
                        </el-tag>
                      </div>
                      <span class="step-count">共 {{ gap.learning_path.length }} 阶段</span>
                    </div>
                  </template>

                  <el-timeline>
                    <el-timeline-item
                      v-for="(stepName, stepIdx) in gap.learning_path"
                      :key="stepIdx"
                      :timestamp="'阶段 ' + (stepIdx + 1)"
                      placement="top"
                      :color="stepIdx === 0 ? '#409eff' : stepIdx === gap.learning_path.length - 1 ? '#67c23a' : '#e6a23c'"
                      :hollow="stepIdx > 0"
                      size="large"
                    >
                      <div class="timeline-content">
                        {{ stepName }}
                      </div>
                    </el-timeline-item>
                  </el-timeline>
                </el-card>
              </div>

              <div class="step-actions">
                <el-button
                  type="primary"
                  size="large"
                  :icon="RefreshRight"
                  @click="handleReset"
                >
                  重新诊断
                </el-button>
                <el-button
                  size="large"
                  :icon="ArrowLeft"
                  @click="step = 3"
                >
                  返回差距报告
                </el-button>
              </div>
            </el-card>
          </template>
        </div>
      </transition>
    </div>
  </MainLayout>
</template>

<style scoped>
.match-page {
  max-width: 960px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 6px;
}

.page-desc {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.steps-wrapper {
  background: #fff;
  padding: 24px 16px 16px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #ebeef5;
}

.step-title {
  font-size: 13px;
  color: #606266;
}

/* ── 步骤过渡动画 ── */
.step-fade-enter-active,
.step-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.step-fade-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.step-fade-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}

.step-content {
  /* ensure transition container has layout */
}

.step-card {
  border: 1px solid #ebeef5;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 16px;
  color: #303133;
}

.field-label {
  display: block;
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 500;
}

/* ── 技能输入 ── */
.manual-skills {
  margin-top: 8px;
}

.skill-input-row {
  display: flex;
  gap: 0;
}

.skill-tags {
  margin-top: 12px;
  min-height: 40px;
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px dashed #dcdfe6;
}

.empty-hint {
  margin-top: 12px;
  color: #c0c4cc;
  font-size: 13px;
  text-align: center;
  padding: 12px;
}

/* ── 我的技能 ── */
.my-skills {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.skills-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
  padding-top: 6px;
  font-weight: 500;
}

.skills-list {
  flex: 1;
}

/* ── 步骤操作栏 ── */
.step-actions {
  margin-top: 24px;
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

/* ── 分数卡片 ── */
.score-card {
  text-align: center;
}

.score-circle {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.score-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.score-label {
  color: #909399;
  font-size: 14px;
  margin-top: -4px;
}

.score-target {
  margin-top: 8px;
}

/* ── 技能卡片 ── */
.skill-card {
  height: 100%;
}

.skill-card-title {
  font-size: 14px;
  font-weight: 600;
}

.skill-tags-mini {
  min-height: 60px;
}

/* ── 差距进度条 ── */
.gap-progress {
  width: 160px;
}

/* ── 学习路径预览 ── */
.learning-path-preview {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

/* ── 评估文本 ── */
.assessment-text {
  font-size: 15px;
  line-height: 1.9;
  color: #303133;
}

/* ── 学习路径卡片 ── */
.learning-paths {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.learning-card {
  transition: box-shadow 0.3s;
}

.learning-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.step-count {
  font-size: 13px;
  color: #909399;
}

.timeline-content {
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
}

/* ── 图例圆点 ── */
.legend-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  vertical-align: middle;
  margin-right: 2px;
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .match-page {
    padding: 0 8px;
  }

  .my-skills {
    flex-direction: column;
    gap: 8px;
  }

  .step-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .skill-card {
    margin-bottom: 12px;
  }
}
</style>
