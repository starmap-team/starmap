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
  Plus, Download, ArrowRight
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
import type { RadarItem } from '@/components/SkillRadar.vue'

// 业务说明：初始化各业务模块的 Pinia Store，用于管理用户数据、简历解析、匹配诊断和学习路径
const userStore = useUserStore()
const resumeStore = useResumeStore()
const matchStore = useMatchStore()
const learningStore = useLearningStore()

// ── Page mode: single or batch ──
// 业务说明：页面支持两种模式——单次匹配（单简历单岗位）和批量匹配（多简历多岗位），通过 Tabs 切换
const pageMode = ref('single')

// 技术说明：ResumeUpload 组件的引用，用于调用其 setAsyncUploader 方法注入异步上传处理器
const resumeUploadRef = ref<InstanceType<typeof ResumeUpload> | null>(null)

// 业务说明：当前步骤索引，0-4 分别对应：上传简历、选岗、雷达对比、差距分析、学习路径
const step = ref(0)
// 业务说明：用户选中的目标岗位名称，用于后续匹配诊断和展示
const targetPositionName = ref('')
// 业务说明：技能雷达图数据，包含岗位要求技能和用户实际技能水平
const radarData = ref<RadarItem[]>([])
// 业务说明：雷达图数据加载状态，用于显示 loading 动画
const radarLoading = ref(false)

// 业务说明：匹配进度动画相关状态，用于诊断过程中的进度条和技能匹配动画展示
const matchProgress = ref(0)
const matchProgressTimer = ref<ReturnType<typeof setInterval> | null>(null)
const matchAnimating = ref(false)
const matchAnimSkills = ref<SkillMatchItem[]>([])
const matchAnimComplete = ref(false)

import { PROFICIENCY_MAP } from '@/utils/proficiency'
// 业务说明：5步向导的标题数组，用于 el-steps 步骤条展示
const stepTitles = ['上传简历', '选择目标岗位', '技能雷达对比', '差距分析报告', '学习路径规划']

// ── Step 0: 上传简历 ──
// 业务说明：处理简历上传，调用简历解析服务提取技能，解析成功后自动进入步骤 1
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

// 业务说明：监听步骤变化，当用户返回 Step 0 时重新挂载上传函数；进入 Step 3 时加载历史诊断记录
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

// 技术说明：将异步上传处理器注入 ResumeUpload 组件，使其能够调用 handleUpload 处理文件
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

// 业务说明：手动输入技能模式，允许用户直接输入技能标签而非上传简历
const skillInput = ref('')
const manualSkills = ref<string[]>([])
// showManualInput: reserved for future use
// const showManualInput = ref(true)

// 业务说明：添加手动输入的技能标签，去重并给出提示
function addManualSkill() {
  const val = skillInput.value.trim()
  if (!val) return
  if (manualSkills.value.includes(val)) { ElMessage.warning('该技能已添加'); return }
  manualSkills.value.push(val)
  skillInput.value = ''
}
// 业务说明：移除已添加的手动技能标签
function removeManualSkill(skill: string) {
  manualSkills.value = manualSkills.value.filter(s => s !== skill)
}
// 业务说明：确认手动输入的技能，保存到用户 Store 并进入步骤 1
function confirmManualSkills() {
  if (!manualSkills.value.length) { ElMessage.warning('请至少添加一个技能'); return }
  userStore.parsedSkills = [...manualSkills.value]
  ElMessage.success('已录入 ' + manualSkills.value.length + ' 项技能')
  step.value = 1
}

// ── Step 1: 选岗 ──
// 业务说明：处理目标岗位选择，从 Neo4j 图数据库获取岗位技能要求，构建雷达图数据
async function handlePositionSelect(pos: { position_id: string; name: string }) {
  targetPositionName.value = pos.name
  radarLoading.value = true
  try {
    // 技术说明：使用岗位名称进行 Neo4j 图数据库查询（Neo4j 通过名称标识岗位）
    const skillData = await matchStore.fetchPositionSkills(pos.name)
    const skills: any[] = skillData?.required_skills ?? []
    // 业务说明：岗位技能为空时不再阻塞流程——降级为空雷达并提示用户，
    // 用户仍可进入下一步（SkillRadar 组件自身有"数据不足"占位）。
    // 这样避免选岗后卡死、无法继续诊断的体验问题（B05）。
    if (skills.length === 0) {
      ElMessage.warning('未获取到岗位技能数据，仍可继续但雷达图将为空')
      radarData.value = []
      step.value = 2
      return
    }
    // 业务说明：构建雷达图数据，初始时用户技能为 0，后续根据简历解析结果填充
    radarData.value = skills.map((s: any) => ({
      skill: s.name,
      required: PROFICIENCY_MAP[s.proficiency] ?? 0.5,
      user: 0,
    }))
    // 业务说明：将用户简历中的技能与岗位要求技能进行匹配，填充用户实际技能水平
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
// 业务说明：触发匹配诊断流程，展示进度动画和技能匹配动画，完成后进入差距分析报告
async function handleStartDiagnosis() {
  matchProgress.value = 0
  matchAnimating.value = true
  matchAnimComplete.value = false
  matchAnimSkills.value = []

  // 技术说明：启动进度条动画，每 300ms 增加随机进度，直到 85%
  if (matchProgressTimer.value) clearInterval(matchProgressTimer.value)
  matchProgressTimer.value = setInterval(() => {
    if (matchProgress.value < 85) matchProgress.value += Math.random() * 12
  }, 300)

  try {
    const skillNames = userStore.parsedSkills
    // 业务说明：从简历解析结果构建技能熟练度映射，用于更精确的匹配计算
    const profMap: Record<string, string> = {}
    if (resumeStore.result?.required_skills) {
      for (const s of resumeStore.result.required_skills) {
        profMap[s.skill] = s.proficiency ?? '熟悉'
      }
    }
    // 业务说明：调用匹配诊断服务，计算用户技能与目标岗位的匹配度
    await matchStore.runMatch(targetPositionName.value, skillNames, profMap)
    matchProgress.value = 100

    // 业务说明：根据匹配结果构建技能匹配动画数据，展示匹配成功和缺失的技能
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
      // 业务说明：将用户未掌握的差距技能也加入动画展示
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
// 业务说明：从匹配 Store 获取诊断结果，包括匹配分数、已匹配技能、技能差距等
const matchResult = computed(() => matchStore.result)
const gapSkills = computed(() => matchResult.value?.skill_gap_detail ?? [])
const matchedSkills = computed(() => matchResult.value?.matched_skills ?? [])
const matchScore = computed(() => matchResult.value?.match_score ?? 0)

// 业务说明：进入学习路径规划步骤
function goToLearning() {
  step.value = 4
}

// ── Step 4: 学习路径 ──
// 业务说明：根据技能差距生成个性化学习路径，将学习步骤数组转换为可视化展示格式
const learningPaths = computed(() => {
  return gapSkills.value.map(g => {
    const pathArr = Array.isArray(g.learning_path) ? g.learning_path : []
    return {
      skill: g.skill,
      importance: g.importance,
      gapLevel: g.gap_level,
      path: pathArr.length > 0 ? pathArr.join(' → ') : '—',
      pathArray: pathArr,
    }
  })
})

// ── 通用 ──
// 业务说明：返回上一步
function goBack() {
  if (step.value > 0) step.value--
}
// 业务说明：重置所有状态，重新开始匹配诊断流程
function resetAll() {
  step.value = 0
  targetPositionName.value = ''
  radarData.value = []
  matchStore.result = null
  matchProgress.value = 0
  manualSkills.value = []
  userStore.clearResume()
}

// 业务说明：导出匹配诊断报告为 JSON 文件，包含完整的匹配结果和差距分析
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
// 业务说明：批量匹配模式的数据绑定，支持多简历与多岗位的一次性匹配评估
const batchPositions = ref('')
const batchResumes = ref('')
const batchCompetitivenessPosition = ref('')

// 业务说明：处理批量匹配请求，将输入的多行文本解析为简历技能组和岗位列表，调用批量匹配服务
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
// 业务说明：根据输入的目标岗位名称，获取该岗位在市场中的竞争力分析数据
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
      <!-- 业务说明：页面标题区域，展示当前页面名称和功能描述 -->
      <div class="page-header">
        <h1 class="page-title">
          匹配诊断
        </h1>
        <p class="page-desc">
          上传简历或输入技能，诊断与目标岗位的匹配度
        </p>
      </div>

      <!-- 业务说明：模式切换 Tabs，支持单次匹配和批量匹配两种模式 -->
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
        <!-- 业务说明：5步向导步骤条，展示当前进度和已完成步骤 -->
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
        <!-- 业务说明：步骤 0 - 简历上传与手动技能输入，支持两种方式录入用户技能 -->
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
                <!-- 业务说明：简历上传区域，支持文件上传和自动解析 -->
                <div class="input-section">
                  <h3 class="is-title">
                    上传简历
                  </h3>
                  <ResumeUpload
                    ref="resumeUploadRef"
                    @upload="handleUploadEvent"
                  />
                </div>
              </el-col>
              <el-col :span="12">
                <!-- 业务说明：手动输入技能区域，支持逐个添加技能标签并确认 -->
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
                    <!-- 业务说明：已添加的手动技能标签列表，支持删除单个标签 -->
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
        <!-- 业务说明：步骤 1 - 目标岗位选择，用户搜索并选择要匹配的目标岗位 -->
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
        <!-- 业务说明：步骤 2 - 技能雷达对比，展示用户技能与岗位要求的可视化对比，可触发诊断 -->
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
            <!-- 业务说明：技能雷达图组件，展示用户技能与岗位要求的对比，loading 时显示加载状态 -->
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

            <!-- 业务说明：技能匹配动画覆盖层，诊断过程中展示技能匹配动画效果 -->
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
        <!-- 业务说明：步骤 3 - 差距分析报告，展示匹配分数、已匹配技能、技能差距明细和诊断历史 -->
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

            <!-- 业务说明：当匹配结果存在时，展示匹配分数、匹配技能、综合评估和技能差距明细 -->
            <div v-if="matchStore.result">
              <!-- Summary — with reveal animation -->
              <!-- 业务说明：报告摘要卡片，展示匹配分数（百分比）、匹配技能标签、综合评估和预计学习时间 -->
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
                  <!-- 业务说明：预计学习时间，仅在返回该字段时展示 -->
                  <div
                    v-if="matchResult?.estimated_learning_time"
                    class="rs-row"
                  >
                    <span class="rs-label">预计学习时间</span>
                    <span class="rs-text">{{ matchResult?.estimated_learning_time }}</span>
                  </div>
                </div>
              </div>

              <!-- 业务说明：技能差距明细表格，展示缺失技能的名称、重要性（必备/加分）、差距程度和推荐学习路径 -->
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
                    <!-- 业务说明：重要性标签，required 为红色"必备"，其他为灰色"加分" -->
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
                    <!-- 业务说明：差距程度标签，根据程度显示不同颜色：完全缺失(红色)/部分掌握(黄色)/其他(绿色) -->
                    <el-tag
                      :type="row.gap_level === '完全缺失' ? 'danger' : row.gap_level === '部分掌握' ? 'warning' : 'success'"
                      size="small"
                    >
                      {{ row.gap_level }}
                    </el-tag>
                  </template>
                </el-table-column>
                <!-- 业务说明：推荐学习路径列，以步骤节点和箭头形式展示学习路径 -->
                <el-table-column label="推荐学习路径">
                  <template #default="{ row }">
                    <div
                      v-if="Array.isArray(row.learning_path) && row.learning_path.length > 0"
                      class="lp-cell"
                    >
                      <div
                        v-for="(step, si) in row.learning_path"
                        :key="si"
                        class="lp-cell-step"
                      >
                        <span
                          class="lp-cell-dot"
                          :class="{ 'lp-cell-dot--final': si === row.learning_path.length - 1 }"
                        />
                        <span class="lp-cell-text">{{ step }}</span>
                        <span
                          v-if="si < row.learning_path.length - 1"
                          class="lp-cell-arrow"
                        >→</span>
                      </div>
                    </div>
                    <span
                      v-else
                      class="lp-cell-empty"
                    >—</span>
                  </template>
                </el-table-column>
              </el-table>

              <!-- 业务说明：操作按钮区域，支持查看学习路径和导出诊断报告 -->
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
            <!-- 业务说明：当匹配结果不存在时，展示空状态提示 -->
            <div
              v-else
              class="step-empty"
            >
              诊断尚未开始，请完成前序步骤
            </div>
          </div>
        </div>

        <!-- 历史记录面板（在 Step 3 下方） -->
        <!-- 业务说明：诊断历史记录表格，展示用户之前的匹配诊断记录，包括目标岗位、匹配分数、匹配技能和时间 -->
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
                  <!-- 业务说明：根据匹配分数显示不同颜色：高分(绿色)/中分(黄色)/低分(红色) -->
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
        <!-- 业务说明：步骤 4 - 学习路径规划，基于技能差距生成个性化的学习路径和时间线 -->
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

            <!-- 业务说明：学习路径统计摘要，展示待学技能总数、必备技能数和加分技能数 -->
            <div class="lp-summary">
              <div class="lp-summary-item">
                <span class="lp-summary-label">待学技能</span>
                <span class="lp-summary-value">{{ learningPaths.length }}</span>
              </div>
              <div class="lp-summary-item">
                <span class="lp-summary-label">必备技能</span>
                <span class="lp-summary-value required">{{ learningPaths.filter(p => p.importance === 'required').length }}</span>
              </div>
              <div class="lp-summary-item">
                <span class="lp-summary-label">加分技能</span>
                <span class="lp-summary-value bonus">{{ learningPaths.filter(p => p.importance === 'bonus').length }}</span>
              </div>
            </div>

            <!-- 业务说明：学习路径时间线，按技能展示学习步骤，必备技能用红色标记，加分技能用灰色标记 -->
            <el-timeline class="lp-timeline">
              <el-timeline-item
                v-for="(item, idx) in learningPaths"
                :key="item.skill"
                :type="item.importance === 'required' ? 'danger' : 'info'"
                :timestamp="item.gapLevel"
                :hollow="item.importance === 'bonus'"
                placement="top"
                size="large"
              >
                <div class="lp-item">
                  <div class="lp-item-header">
                    <span class="lp-item-index">{{ idx + 1 }}.</span>
                    <strong class="lp-item-skill">{{ item.skill }}</strong>
                    <el-tag
                      :type="item.importance === 'required' ? 'danger' : 'info'"
                      size="small"
                      effect="dark"
                      class="lp-item-tag"
                    >
                      {{ item.importance === 'required' ? '必备' : '加分' }}
                    </el-tag>
                  </div>
                  <!-- 业务说明：技能的学习步骤，使用 el-steps 组件展示学习路径，最后一步用目标图标标记 -->
                  <div
                    v-if="item.pathArray.length > 0"
                    class="lp-item-steps"
                  >
                    <el-steps
                      :active="item.pathArray.length - 1"
                      finish-status="success"
                      :space="60"
                      :class="'lp-steps--' + (item.pathArray.length <= 3 ? 'compact' : 'dense')"
                    >
                      <el-step
                        v-for="(stepName, si) in item.pathArray"
                        :key="si"
                        :title="stepName"
                        :icon="si === item.pathArray.length - 1 ? '🎯' : undefined"
                      />
                    </el-steps>
                  </div>
                  <!-- 业务说明：当技能没有前置依赖时，显示可直接学习的提示 -->
                  <div
                    v-else
                    class="lp-item-path lp-path-empty"
                  >
                    <span class="lp-path-label">无前置依赖，可直接学习</span>
                  </div>
                </div>
              </el-timeline-item>
            </el-timeline>

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
      <!-- 业务说明：批量匹配模式，支持多简历与多岗位的批量匹配评估和竞争力分析 -->
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

            <!-- 业务说明：批量匹配输入区域，左侧输入简历技能（每行一组，逗号分隔），右侧输入目标岗位 -->
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

            <!-- 业务说明：批量匹配结果表格，展示每条简历与对应岗位的匹配分数、匹配技能和缺失技能 -->
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

        <!-- 业务说明：竞争力分析模块，输入目标岗位后获取该岗位在市场中的竞争力分析数据 -->
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

            <!-- 业务说明：竞争力分析输入框，输入岗位名称后触发分析 -->
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

            <!-- 业务说明：竞争力分析结果展示，使用 CompetitivenessChart 组件可视化展示 -->
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

/* ── Learning Path Timeline ── */
.lp-summary {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 4%, var(--card)), var(--card));
  border: 1px solid color-mix(in srgb, var(--primary) 12%, var(--border));
  border-radius: var(--radius-xl);
  margin-bottom: var(--space-5);
}
.lp-summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  gap: var(--space-1);
}
.lp-summary-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  font-weight: 500;
}
.lp-summary-value {
  font-size: var(--font-size-2xl);
  font-weight: 800;
  color: var(--foreground);
  line-height: 1;
}
.lp-summary-value.required { color: var(--danger); }
.lp-summary-value.bonus { color: var(--info); }

/* ── Learning Path Cell (in gap table) ── */
.lp-cell {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
}
.lp-cell-step {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.lp-cell-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--muted-foreground);
  flex-shrink: 0;
}
.lp-cell-dot--final {
  background: var(--success);
}
.lp-cell-text {
  font-size: var(--font-size-xs);
  color: var(--foreground);
  white-space: nowrap;
}
.lp-cell-arrow {
  color: var(--muted-foreground);
  font-size: 10px;
  margin: 0 2px;
}
.lp-cell-empty {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
}

.lp-timeline {
  padding: var(--space-2) 0;
}
.lp-item {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: var(--space-4) var(--space-5);
  transition: box-shadow 0.2s;
}
.lp-item:hover {
  box-shadow: var(--shadow-md);
}
.lp-item-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.lp-item-index {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  font-weight: 500;
  min-width: 1.5em;
}
.lp-item-skill {
  font-size: var(--font-size-base);
  color: var(--foreground);
  flex: 1;
}
.lp-item-tag {
  flex-shrink: 0;
}
.lp-item-steps {
  padding-left: calc(1.5em + var(--space-2));
}
.lp-item-steps :deep(.el-step__title) {
  font-size: var(--font-size-xs);
  line-height: 1.4;
}
.lp-item-steps :deep(.el-step__head) {
  padding-right: 6px;
}
.lp-steps--compact :deep(.el-step) {
  flex-basis: auto !important;
}
.lp-steps--dense :deep(.el-step__title) {
  font-size: 10px;
}
.lp-item-path {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-1-5);
  padding-left: calc(1.5em + var(--space-2));
}
.lp-path-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  font-weight: 500;
  white-space: nowrap;
}
.lp-path-step {
  font-size: var(--font-size-xs);
}
.lp-path-step.lp-path-current {
  --el-tag-bg-color: color-mix(in srgb, var(--success) 15%, transparent);
  --el-tag-text-color: var(--success);
  --el-tag-border-color: color-mix(in srgb, var(--success) 30%, transparent);
}
.lp-path-arrow {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--success);
  font-weight: 600;
  white-space: nowrap;
}
.lp-path-empty {
  opacity: 0.7;
}
.lp-path-empty .lp-path-label {
  font-style: italic;
}
</style>
