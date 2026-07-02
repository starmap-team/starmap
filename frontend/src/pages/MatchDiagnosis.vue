<script setup lang="ts">
/**
 * 匹配诊断页 — 5步向导
 * Step 0: 上传简历 / 手动输入技能
 * Step 1: 选择目标岗位
 * Step 2: 技能雷达对比
 * Step 3: 差距分析报告
 * Step 4: 学习路径规划
 */
import { ref, computed, onMounted, watch, nextTick } from 'vue'
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
import CompetitivenessChart from '@/components/CompetitivenessChart.vue'
import SkillMatchAnimation from '@/components/SkillMatchAnimation.vue'
import LoadingPulse from '@/components/LoadingPulse.vue'
import type { SkillMatchItem } from '@/components/SkillMatchAnimation.vue'
import { useUserStore } from '@/stores/user'
import { useResumeStore } from '@/stores/resume'
import { useMatchStore } from '@/stores/match'
import { useLearningStore } from '@/stores/learning'
import request from '@/api/request'
import type { RadarItem } from '@/components/SkillRadar.vue'

const userStore = useUserStore()
const resumeStore = useResumeStore()
const matchStore = useMatchStore()
const learningStore = useLearningStore()

// ── Page mode: single or batch ──
const pageMode = ref('single')

const resumeUploadRef = ref<InstanceType<typeof ResumeUpload> | null>(null)

const step = ref(0)
const targetPositionName = ref('')
const radarData = ref<RadarItem[]>([])
const radarLoading = ref(false)

const matchProgress = ref(0)
const matchProgressTimer = ref<ReturnType<typeof setInterval> | null>(null)
const matchAnimating = ref(false)
const matchAnimSkills = ref<SkillMatchItem[]>([])
const matchAnimComplete = ref(false)

const PROFICIENCY_MAP: Record<string, number> = { '精通': 0.9, '熟悉': 0.65, '了解': 0.35 }
const stepTitles = ['上传简历', '选择目标岗位', '技能雷达对比', '差距分析报告', '学习路径规划']

// ── Step 0: 上传简历 ──
async function handleUpload(file: File) {
  await resumeStore.parseResume(file)
  if (!resumeStore.result) {
    throw new Error('解析结果为空')
  }
  userStore.setResume(file.name, resumeStore.result.required_skills.map(s => s.skill) ?? [])
  // 短暂停留让用户看到"解析完成"状态，再切换步骤
  await new Promise(resolve => setTimeout(resolve, 600))
  ElMessage.success('简历解析完成，识别 ' + userStore.parsedSkills.length + ' 项技能')
  step.value = 1
}

onMounted(async () => {
  await nextTick()
  setAsyncUploader()
})

// 当用户返回 Step 0（如点击"重新开始"）时重新挂载上传函数
// 当进入 Step 3 时加载诊断历史
watch(() => step.value, async (newStep) => {
  if (newStep === 0) {
    await nextTick()
    setAsyncUploader()
  }
  if (newStep === 3) {
    matchStore.fetchHistory()
  }
})

function setAsyncUploader() {
  if (resumeUploadRef.value) {
    resumeUploadRef.value.setAsyncUploader(handleUpload)
  }
}

// 备用：通过 emit 事件处理上传
function handleUploadEvent(file: File) {
  // 不 catch 错误，让 startUpload 处理
  handleUpload(file)
}

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
    // Use position name for Neo4j lookup (Neo4j identifies positions by name)
    const skillJson = await request.get(`/graph/position/${encodeURIComponent(pos.name)}/skills`) as any
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
  } catch (e: any) {
    ElMessage.warning(`岗位技能请求失败: ${e?.message ?? '未知错误'}`)
  } finally {
    radarLoading.value = false
  }
}

// ── Step 2: 开始诊断（带进度动画 + 技能匹配动画） ──
async function handleStartDiagnosis() {
  matchProgress.value = 0
  matchAnimating.value = true
  matchAnimComplete.value = false
  matchAnimSkills.value = []

  if (matchProgressTimer.value) clearInterval(matchProgressTimer.value)
  matchProgressTimer.value = setInterval(() => {
    if (matchProgress.value < 85) matchProgress.value += Math.random() * 12
  }, 300)

  try {
    const skillNames = userStore.parsedSkills
    // Build proficiency map from resume result if available
    const profMap: Record<string, string> = {}
    if (resumeStore.result?.required_skills) {
      for (const s of resumeStore.result.required_skills) {
        profMap[s.skill] = s.proficiency ?? '熟悉'
      }
    }
    await matchStore.runMatch(targetPositionName.value, skillNames, profMap)
    matchProgress.value = 100

    // Build animation skills from result
    const result = matchStore.result
    if (result) {
      const matchedSet = new Set(result.matched_skills ?? [])
      const gapSet = new Set((result.skill_gap_detail ?? []).map((g: any) => g.skill))
      const allSkills = [
        ...skillNames.map((s: string) => ({
          name: s,
          matched: matchedSet.has(s),
          score: matchedSet.has(s) ? result.match_score ?? 0.85 : 0,
        })),
      ]
      // Add gap skills not in user skills
      for (const g of (result.skill_gap_detail ?? [])) {
        if (!skillNames.includes(g.skill)) {
          allSkills.push({ name: g.skill, matched: false, score: 0 })
        }
      }
      matchAnimSkills.value = allSkills
    }

    step.value = 3
  } catch (e: any) {
    ElMessage.error('诊断请求失败: ' + (e?.message ?? '未知错误'))
    matchAnimating.value = false
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
    match_id: matchResult.value?.match_id,
    target_position: targetPositionName.value,
    match_score: matchScore.value,
    matched_skills: matchedSkills.value,
    missing_required: matchResult.value?.missing_required ?? [],
    missing_bonus: matchResult.value?.missing_bonus ?? [],
    gap_skills: gapSkills.value,
    skill_gap_detail: matchResult.value?.skill_gap_detail ?? [],
    recommendations: matchResult.value?.recommendations ?? [],
    learning_paths: learningPaths.value,
    overall_assessment: matchResult.value?.overall_assessment ?? '',
    estimated_learning_time: matchResult.value?.estimated_learning_time ?? '',
    exported_at: new Date().toISOString(),
  }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `match-report-${targetPositionName.value}.json`; a.click()
  URL.revokeObjectURL(url)
}

// ── 批量匹配 ──
const batchPositions = ref('')
const batchResumes = ref('')
const batchCompetitivenessPosition = ref('')

async function handleBatchMatch() {
  const positions = batchPositions.value.split('\n').map(s => s.trim()).filter(Boolean)
  const resumes = batchResumes.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!positions.length || !resumes.length) {
    ElMessage.warning('请输入至少一个简历技能组和一个目标岗位')
    return
  }
  try {
    await learningStore.runBatchMatch(
      resumes.map((r, i) => ({
        skills: r.split(',').map(s => s.trim()),
        position: positions[i % positions.length],
      }))
    )
    ElMessage.success(`批量匹配完成，共 ${learningStore.batchResults.length} 条结果`)
  } catch {
    // error handled by store
  }
}

// ── 竞争力分析 ──
async function handleCompetitiveness() {
  const pos = batchCompetitivenessPosition.value.trim()
  if (!pos) {
    ElMessage.warning('请输入目标岗位名称')
    return
  }
  try {
    await learningStore.fetchCompetitiveness(pos)
  } catch {
    // error handled by store
  }
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

      <!-- Mode Tabs -->
      <el-tabs
        v-model="pageMode"
        class="mode-tabs"
      >
        <el-tab-pane
          label="单次匹配"
          name="single"
        />
        <el-tab-pane
          label="批量匹配"
          name="batch"
        />
      </el-tabs>

      <!-- Single Match (existing wizard) -->
      <template v-if="pageMode === 'single'">
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
                <ResumeUpload ref="resumeUploadRef" @upload="handleUploadEvent" />
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

          <!-- Match Animation Overlay -->
          <div
            v-if="matchAnimating && matchAnimSkills.length > 0"
            class="match-anim-section"
          >
            <h3 class="match-anim-title">
              <LoadingPulse size="small" />
              技能匹配中...
            </h3>
            <SkillMatchAnimation
              :skills="matchAnimSkills"
              :auto-play="true"
              :interval="350"
              @complete="matchAnimComplete = true"
            />
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
            <!-- Summary — with reveal animation -->
            <div class="report-summary anim-scale-in">
              <div class="rs-score">
                <span class="rs-value">{{ Math.round((matchStore.result.match_score ?? 0) * 100) }}</span>
                <span class="rs-unit">%</span>
              </div>
              <div class="rs-detail">
                <div class="rs-row">
                  <span class="rs-label">匹配技能</span>
                  <div class="rs-tags stagger">
                    <el-tag
                      v-for="s in matchedSkills"
                      :key="s"
                      type="success"
                      size="small"
                      class="anim-fade-in-up"
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

      <!-- 历史记录面板（在 Step 3 下方） -->
      <div
        v-if="step === 3 && matchStore.historyList.length > 0"
        class="step-content"
      >
        <div class="step-card">
          <div class="sc-header">
            <h2 class="sc-title">
              诊断历史
            </h2>
            <p class="sc-desc">
              最近的匹配诊断记录
            </p>
          </div>
          <el-table
            :data="matchStore.historyList"
            stripe
            size="small"
            class="full-width-table"
          >
            <el-table-column
              prop="target_position"
              label="目标岗位"
              min-width="140"
            />
            <el-table-column
              label="匹配分数"
              width="100"
            >
              <template #default="{ row }">
                <span :class="row.match_score >= 0.7 ? 'score-high' : row.match_score >= 0.4 ? 'score-mid' : 'score-low'">
                  {{ Math.round(row.match_score * 100) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column
              label="匹配技能"
              min-width="200"
            >
              <template #default="{ row }">
                <el-tag
                  v-for="s in row.matched_skills?.slice(0, 5)"
                  :key="s"
                  size="small"
                  type="success"
                  class="mr-1"
                >
                  {{ s }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="时间"
              width="160"
            >
              <template #default="{ row }">
                {{ row.created_at ? new Date(row.created_at).toLocaleString() : '—' }}
              </template>
            </el-table-column>
          </el-table>
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
      </template>

      <!-- Batch Match -->
      <template v-if="pageMode === 'batch'">
        <div class="step-content">
          <div class="step-card">
            <div class="sc-header">
              <h2 class="sc-title">
                批量匹配
              </h2>
              <p class="sc-desc">
                多简历 vs 多岗位，批量评估匹配度
              </p>
            </div>

            <el-row :gutter="20">
              <el-col :span="12">
                <div class="batch-input-group">
                  <h3 class="is-title">
                    简历技能（每行一个，逗号分隔技能）
                  </h3>
                  <el-input
                    v-model="batchResumes"
                    type="textarea"
                    :rows="5"
                    placeholder="JavaScript, TypeScript, Vue 3&#10;Python, Django, PostgreSQL&#10;Java, Spring Boot, MySQL"
                  />
                </div>
              </el-col>
              <el-col :span="12">
                <div class="batch-input-group">
                  <h3 class="is-title">
                    目标岗位（每行一个，与简历一一对应）
                  </h3>
                  <el-input
                    v-model="batchPositions"
                    type="textarea"
                    :rows="5"
                    placeholder="前端工程师&#10;后端工程师&#10;全栈工程师"
                  />
                </div>
              </el-col>
            </el-row>

            <div class="step-actions">
              <el-button
                type="primary"
                size="large"
                :icon="DataAnalysis"
                :loading="learningStore.batchLoading"
                @click="handleBatchMatch"
              >
                开始批量匹配
              </el-button>
            </div>

            <!-- Batch Results -->
            <div
              v-if="learningStore.batchResults.length"
              class="batch-results"
            >
              <h3 class="table-title">
                批量匹配结果
              </h3>
              <el-table
                :data="learningStore.batchResults"
                stripe
                class="full-width-table"
              >
                <el-table-column
                  prop="resume_name"
                  label="简历"
                  min-width="120"
                />
                <el-table-column
                  prop="position_name"
                  label="目标岗位"
                  min-width="140"
                />
                <el-table-column
                  label="匹配分数"
                  width="120"
                >
                  <template #default="{ row }">
                    <span :class="row.match_score >= 0.7 ? 'score-high' : row.match_score >= 0.4 ? 'score-mid' : 'score-low'">
                      {{ Math.round(row.match_score * 100) }}%
                    </span>
                  </template>
                </el-table-column>
                <el-table-column
                  label="匹配技能"
                  min-width="200"
                >
                  <template #default="{ row }">
                    <el-tag
                      v-for="s in row.matched_skills?.slice(0, 4)"
                      :key="s"
                      size="small"
                      type="success"
                      class="mr-1"
                    >
                      {{ s }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column
                  label="缺失技能"
                  min-width="200"
                >
                  <template #default="{ row }">
                    <el-tag
                      v-for="s in row.gap_skills?.slice(0, 4)"
                      :key="s"
                      size="small"
                      type="danger"
                      class="mr-1"
                    >
                      {{ s }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </div>

        <!-- 竞争力分析 -->
        <div class="step-content">
          <div class="step-card">
            <div class="sc-header">
              <h2 class="sc-title">
                竞争力分析
              </h2>
              <p class="sc-desc">
                查看你的技能在市场中的竞争力水平
              </p>
            </div>

            <div class="competitiveness-input">
              <el-input
                v-model="batchCompetitivenessPosition"
                placeholder="输入目标岗位名称，如：前端工程师"
                size="large"
                clearable
                @keyup.enter="handleCompetitiveness"
              >
                <template #append>
                  <el-button
                    :icon="DataAnalysis"
                    :loading="learningStore.competitivenessLoading"
                    @click="handleCompetitiveness"
                  >
                    分析
                  </el-button>
                </template>
              </el-input>
            </div>

            <div
              v-if="learningStore.competitiveness.length"
              class="competitiveness-result"
            >
              <CompetitivenessChart :data="learningStore.competitiveness" />
            </div>
          </div>
        </div>
      </template>
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
.mr-1 { margin-right: var(--space-1); }
.score-high { color: var(--success); font-weight: 700; }
.score-mid { color: var(--warning); font-weight: 700; }
.score-low { color: var(--danger); font-weight: 700; }

/* ── Mode Tabs ── */
.mode-tabs {
  margin-bottom: var(--space-5);
}
.mode-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

/* ── Batch Match ── */
.batch-input-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.batch-results {
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border);
}

/* ── Competitiveness ── */
.competitiveness-input {
  max-width: 500px;
  margin-bottom: var(--space-6);
}
.competitiveness-result {
  margin-top: var(--space-4);
}

/* ── Match Animation Section ── */
.match-anim-section {
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border);
  animation: fadeInUp 0.4s var(--ease-out);
}
.match-anim-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin-bottom: var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

@media (max-width: 768px) {
  .match-page { max-width: 100%; }
}
</style>