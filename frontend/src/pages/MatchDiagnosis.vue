<script setup lang="ts">
/**
 * 匹配诊断页 — 5步向导
 * Step 0: 上传简历 / 手动输入技能
 * Step 1: 选择目标岗位
 * Step 2: 技能雷达对比
 * Step 3: 差距分析报告
 * Step 4: 学习路径规划
 */
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  DataAnalysis, Guide, RefreshRight,
  Plus, Download
} from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])
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

const resumeUploadRef = ref<InstanceType<typeof ResumeUpload> | null>(null)

const step = ref(0)
const targetPositionName = ref('')
const radarData = ref<RadarItem[]>([])
const radarLoading = ref(false)

const matchProgress = ref(0)
const matchProgressTimer = ref<ReturnType<typeof setInterval> | null>(null)

const PROFICIENCY_MAP: Record<string, number> = { '精通': 0.9, '熟悉': 0.65, '了解': 0.35 }
const stepTitles = ['上传简历', '选择目标岗位', '技能雷达对比', '差距分析报告', '学习路径规划']

// ── Step 0: 上传简历 ──
async function handleUpload(file: File) {
  await resumeStore.parseResume(file)
  userStore.setResume(file.name, resumeStore.result?.required_skills.map(s => s.skill) ?? [])
  ElMessage.success('简历解析完成，识别 ' + userStore.parsedSkills.length + ' 项技能')
  step.value = 1
}

onMounted(() => {
  if (resumeUploadRef.value) {
    resumeUploadRef.value.setAsyncUploader(handleUpload)
  }
})

// 手动输入技能
const skillInput = ref('')
const manualSkills = ref<string[]>([])
// showManualInput: reserved for future use
// const showManualInput = ref(true)

function addManualSkill() {
  const val = skillInput.value.trim()
  if (!val) return
  if (manualSkills.value.includes(val)) { ElMessage.warning('该技能已添加'); return }
  manualSkills.value.push(val)
  skillInput.value = ''
}
function removeManualSkill(skill: string) {
  manualSkills.value = manualSkills.value.filter(s => s !== skill)
}
function confirmManualSkills() {
  if (!manualSkills.value.length) { ElMessage.warning('请至少添加一个技能'); return }
  userStore.parsedSkills = [...manualSkills.value]
  ElMessage.success('已录入 ' + manualSkills.value.length + ' 项技能')
  step.value = 1
}

// ── Step 1: 选岗 ──
async function handlePositionSelect(pos: { position_id: string; name: string }) {
  targetPositionName.value = pos.name
  radarLoading.value = true
  try {
    const skillRes = await fetch(`/api/v1/graph/position/${encodeURIComponent(pos.position_id)}/skills`)
    if (!skillRes.ok) {
      ElMessage.warning(`岗位技能请求失败 (${skillRes.status})`)
      return
    }
    const skillJson = await skillRes.json()
    const skills: any[] = skillJson?.skills ?? []
    if (skills.length === 0) {
      ElMessage.warning('未获取到岗位技能数据')
      return
    }
    radarData.value = skills.map((s: any) => ({
      skill: s.name,
      required: PROFICIENCY_MAP[s.proficiency] ?? 0.5,
      user: 0,
    }))
    const userSkillSource = resumeStore.result?.required_skills ?? userStore.parsedSkills.map(s => ({ skill: s, proficiency: '熟悉' }))
    if (userSkillSource.length) {
      const userSkills = new Map(userSkillSource.map((s: any) => [s.skill, PROFICIENCY_MAP[s.proficiency] ?? 0.5]))
      radarData.value = radarData.value.map(item => ({ ...item, user: userSkills.get(item.skill) ?? 0 }))
    }
    step.value = 2
  } finally {
    radarLoading.value = false
  }
}

// ── Step 2: 开始诊断（带进度动画） ──
async function handleStartDiagnosis() {
  matchProgress.value = 0
  if (matchProgressTimer.value) clearInterval(matchProgressTimer.value)
  matchProgressTimer.value = setInterval(() => {
    if (matchProgress.value < 90) matchProgress.value += Math.random() * 15
  }, 300)

  try {
    const skillNames = userStore.parsedSkills
    await matchStore.runMatch(targetPositionName.value, skillNames)
    matchProgress.value = 100
    step.value = 3
  } catch (e: any) {
    ElMessage.error('诊断请求失败: ' + (e?.message ?? '未知错误'))
  } finally {
    if (matchProgressTimer.value) {
      clearInterval(matchProgressTimer.value)
      matchProgressTimer.value = null
    }
  }
}

// ── Step 3: 差距分析结果 ──
const matchResult = computed(() => matchStore.result)
const gapSkills = computed(() => matchResult.value?.skill_gap_detail ?? [])
const matchedSkills = computed(() => matchResult.value?.matched_skills ?? [])
const matchScore = computed(() => matchResult.value?.match_score ?? 0)

function goToLearning() {
  step.value = 4
}

// ── Step 4: 学习路径 ──
const learningPaths = computed(() => {
  return gapSkills.value.map(g => ({
    skill: g.skill,
    importance: g.importance,
    gapLevel: g.gap_level,
    path: Array.isArray(g.learning_path) ? g.learning_path.join(' → ') : String(g.learning_path ?? ''),
  }))
})

// ── 通用 ──
function goBack() {
  if (step.value > 0) step.value--
}
function resetAll() {
  step.value = 0
  targetPositionName.value = ''
  radarData.value = []
  matchStore.result = null
  matchProgress.value = 0
  manualSkills.value = []
  userStore.clearResume()
}

function exportReport() {
  const report = {
    position: targetPositionName.value,
    score: matchScore.value,
    matched: matchedSkills.value,
    gaps: gapSkills.value,
    learning: learningPaths.value,
    assessment: matchResult.value?.overall_assessment ?? '',
  }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `match-report-${targetPositionName.value}.json`; a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <MainLayout>
    <div class="match-page animate-fade-in">
      <!-- Page header -->
      <div class="page-header">
        <h1 class="page-title">
          匹配诊断
        </h1>
        <p class="page-desc">
          上传简历或输入技能，诊断与目标岗位的匹配度
        </p>
      </div>

      <!-- Steps -->
      <el-steps
        :active="step"
        finish-status="success"
        class="steps-bar"
        align-center
      >
        <el-step
          v-for="title in stepTitles"
          :key="title"
          :title="title"
        />
      </el-steps>

      <!-- Step 0: Upload/Input -->
      <div
        v-if="step === 0"
        class="step-content"
      >
        <div class="step-card grain">
          <div class="sc-header">
            <h2 class="sc-title">
              录入你的技能
            </h2>
            <p class="sc-desc">
              上传简历自动解析，或手动输入技能标签
            </p>
          </div>

          <el-row :gutter="20">
            <el-col :span="12">
              <div class="input-section">
                <h3 class="is-title">
                  上传简历
                </h3>
                <ResumeUpload ref="resumeUploadRef" />
              </div>
            </el-col>
            <el-col :span="12">
              <div class="input-section">
                <h3 class="is-title">
                  手动输入技能
                </h3>
                <div class="manual-input">
                  <el-input
                    v-model="skillInput"
                    placeholder="输入技能名称，回车添加"
                    size="large"
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
                  <div
                    v-if="manualSkills.length"
                    class="skill-tags"
                  >
                    <el-tag
                      v-for="s in manualSkills"
                      :key="s"
                      closable
                      size="default"
                      @close="removeManualSkill(s)"
                    >
                      {{ s }}
                    </el-tag>
                  </div>
                  <el-button
                    v-if="manualSkills.length"
                    type="primary"
                    class="skill-confirm-action"
                    @click="confirmManualSkills"
                  >
                    确认 {{ manualSkills.length }} 项技能
                  </el-button>
                </div>
              </div>
            </el-col>
          </el-row>
        </div>
      </div>

      <!-- Step 1: Select position -->
      <div
        v-if="step === 1"
        class="step-content"
      >
        <div class="step-card">
          <div class="sc-header">
            <h2 class="sc-title">
              选择目标岗位
            </h2>
            <p class="sc-desc">
              搜索并选择你要匹配的目标岗位
            </p>
          </div>
          <PositionSearch @select="handlePositionSelect" />
        </div>
      </div>

      <!-- Step 2: Radar comparison -->
      <div
        v-if="step === 2"
        class="step-content"
      >
        <div class="step-card">
          <div class="sc-header">
            <div class="sc-header-row">
              <div>
                <h2 class="sc-title">
                  技能雷达对比
                </h2>
                <p class="sc-desc">
                  你的技能 vs {{ targetPositionName }} 岗位要求
                </p>
              </div>
              <el-button
                text
                @click="step = 1"
              >
                ← 返回选岗
              </el-button>
            </div>
          </div>
          <div v-loading="radarLoading">
            <SkillRadar
              :data="radarData"
              :position-name="targetPositionName"
            />
          </div>
          <div class="step-actions">
            <el-button
              type="primary"
              size="large"
              :icon="DataAnalysis"
              @click="handleStartDiagnosis"
            >
              开始诊断
            </el-button>
          </div>
        </div>
      </div>

      <!-- Step 3: Gap analysis report -->
      <div
        v-if="step === 3"
        class="step-content"
      >
        <div class="step-card">
          <div class="sc-header">
            <div class="sc-header-row">
              <div>
                <h2 class="sc-title">
                  差距分析报告
                </h2>
                <p class="sc-desc">
                  综合评估你的岗位匹配度
                </p>
              </div>
              <el-button
                text
                @click="goBack"
              >
                ← 返回
              </el-button>
            </div>
          </div>

          <div v-if="matchStore.result">
            <!-- Summary -->
            <div class="report-summary">
              <div class="rs-score">
                <span class="rs-value">{{ Math.round((matchStore.result.match_score ?? 0) * 100) }}</span>
                <span class="rs-unit">%</span>
              </div>
              <div class="rs-detail">
                <div class="rs-row">
                  <span class="rs-label">匹配技能</span>
                  <div class="rs-tags">
                    <el-tag
                      v-for="s in matchedSkills"
                      :key="s"
                      type="success"
                      size="small"
                    >
                      {{ s }}
                    </el-tag>
                    <span
                      v-if="!matchedSkills.length"
                      class="rs-empty"
                    >无</span>
                  </div>
                </div>
                <div class="rs-row">
                  <span class="rs-label">综合评估</span>
                  <span class="rs-text">{{ matchResult?.overall_assessment ?? '等待评估结果生成' }}</span>
                </div>
                <div
                  v-if="matchResult?.estimated_learning_time"
                  class="rs-row"
                >
                  <span class="rs-label">预计学习时间</span>
                  <span class="rs-text">{{ matchResult?.estimated_learning_time }}</span>
                </div>
              </div>
            </div>

            <!-- Gap table -->
            <h3 class="table-title">
              技能差距明细
            </h3>
            <el-table
              :data="gapSkills"
              stripe
              class="full-width-table"
            >
              <el-table-column
                prop="skill"
                label="技能"
                min-width="140"
              />
              <el-table-column
                label="重要性"
                width="100"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="row.importance === 'required' ? 'danger' : 'info'"
                    size="small"
                  >
                    {{ row.importance === 'required' ? '必备' : '加分' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                label="差距程度"
                width="120"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="row.gap_level === '完全缺失' ? 'danger' : row.gap_level === '部分掌握' ? 'warning' : 'success'"
                    size="small"
                  >
                    {{ row.gap_level }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="推荐学习路径">
                <template #default="{ row }">
                  {{ Array.isArray(row.learning_path) ? row.learning_path.join(' → ') : (row.learning_path ?? '—') }}
                </template>
              </el-table-column>
            </el-table>

            <div class="step-actions">
              <el-button
                type="primary"
                size="large"
                :icon="Guide"
                @click="goToLearning"
              >
                查看学习路径
              </el-button>
              <el-button
                size="large"
                :icon="Download"
                @click="exportReport"
              >
                导出报告
              </el-button>
            </div>
          </div>
          <div
            v-else
            class="step-empty"
          >
            诊断尚未开始，请完成前序步骤
          </div>
        </div>
      </div>

      <!-- Step 4: Learning path -->
      <div
        v-if="step === 4"
        class="step-content"
      >
        <div class="step-card">
          <div class="sc-header">
            <div class="sc-header-row">
              <div>
                <h2 class="sc-title">
                  学习路径规划
                </h2>
                <p class="sc-desc">
                  基于技能差距的个性化学习建议
                </p>
              </div>
              <el-button
                text
                @click="goBack"
              >
                ← 返回
              </el-button>
            </div>
          </div>
          <el-table
            :data="learningPaths"
            stripe
            class="full-width-table"
          >
            <el-table-column
              prop="skill"
              label="技能"
              min-width="140"
            />
            <el-table-column
              label="优先级"
              width="100"
            >
              <template #default="{ row }">
                <el-tag
                  :type="row.importance === 'required' ? 'danger' : 'info'"
                  size="small"
                >
                  {{ row.importance === 'required' ? '必备' : '加分' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="差距"
              width="100"
            >
              <template #default="{ row }">
                <el-tag
                  :type="row.gapLevel === '完全缺失' ? 'danger' : 'warning'"
                  size="small"
                >
                  {{ row.gapLevel }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              prop="path"
              label="推荐学习路径"
            />
          </el-table>
          <div class="step-actions">
            <el-button
              size="large"
              :icon="RefreshRight"
              @click="resetAll"
            >
              重新开始
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.match-page {
  max-width: 960px;
  margin: 0 auto;
}
.page-header {
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
.steps-bar {
  margin-bottom: var(--space-6);
}
.step-content {
  animation: fade-in-up 0.35s var(--ease-out);
}
@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.step-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-2xl);
  padding: var(--space-8);
  box-shadow: var(--shadow-xs);
  position: relative;
  overflow: hidden;
}
.step-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary), var(--chart-2));
  opacity: 0.8;
}
.sc-header {
  margin-bottom: var(--space-6);
}
.sc-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.sc-title {
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}
.sc-desc {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}
.input-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.is-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
}
.manual-input {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.step-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
  margin-top: var(--space-6);
}
.step-empty {
  text-align: center;
  color: var(--muted-foreground);
  padding: var(--space-10) 0;
  font-size: var(--font-size-sm);
}

/* ── Report Summary ── */
.report-summary {
  display: flex;
  gap: var(--space-6);
  padding: var(--space-6);
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 4%, var(--card)), var(--card));
  border: 1px solid color-mix(in srgb, var(--primary) 12%, var(--border));
  border-radius: var(--radius-2xl);
  margin-bottom: var(--space-6);
  position: relative;
}
.report-summary::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--primary), var(--chart-2));
  border-radius: 2px 2px 0 0;
}
.rs-score {
  display: flex;
  align-items: baseline;
  flex-shrink: 0;
}
.rs-value {
  font-size: 3rem;
  font-weight: 900;
  background: linear-gradient(135deg, var(--primary), var(--chart-1));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
}
.rs-unit {
  font-size: var(--font-size-xl);
  color: var(--muted-foreground);
  margin-left: var(--space-1);
  font-weight: 600;
}
.rs-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-2-5);
}
.rs-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  font-size: var(--font-size-sm);
}
.rs-label {
  color: var(--muted-foreground);
  min-width: 80px;
  flex-shrink: 0;
  font-weight: 500;
}
.rs-text {
  color: var(--foreground);
  line-height: var(--leading-relaxed);
}
.rs-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
.rs-empty {
  color: var(--muted-foreground);
}
.table-title {
  font-size: var(--font-size-base);
  font-weight: 700;
  color: var(--foreground);
  margin: var(--space-6) 0 var(--space-3);
  letter-spacing: var(--tracking-tight);
}
.skill-confirm-action { margin-top: var(--space-4); }
.full-width-table { width: 100%; }
</style>