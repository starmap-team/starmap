<script setup lang="ts">
/**
 * 匹配诊断页 — 5步向导
 * Step 0: 上传简历 / 手动输入技能
 * Step 1: 选择目标岗位
 * Step 2: 技能雷达对比
 * Step 3: 差距分析报告 → GapAnalysisReport.vue
 * Step 4: 学习路径规划 → LearningPathPlan.vue
 */
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Plus } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])
import MainLayout from '@/layouts/MainLayout.vue'
import ResumeUpload from '@/components/ResumeUpload.vue'
import PositionSearch from '@/components/PositionSearch.vue'
import SkillRadar from '@/components/SkillRadar.vue'
import SkillMatchAnimation from '@/components/SkillMatchAnimation.vue'
import LoadingPulse from '@/components/LoadingPulse.vue'
import MatchBatchMode from '@/components/MatchBatchMode.vue'
import GapAnalysisReport from '@/components/GapAnalysisReport.vue'
import LearningPathPlan from '@/components/LearningPathPlan.vue'
import MatchFlow from '@/components/MatchFlow.vue'
import MatchTrustGuide from '@/components/MatchTrustGuide.vue'
import BusinessBanner from '@/components/BusinessBanner.vue'
import type { SkillMatchItem } from '@/components/SkillMatchAnimation.vue'
import { useUserStore } from '@/stores/user'
import { useResumeStore } from '@/stores/resume'
import { useMatchStore } from '@/stores/match'
import { useLearningStore } from '@/stores/learning'
import { useRouter, useRoute } from 'vue-router'
import type { RadarItem } from '@/components/SkillRadar.vue'

const userStore = useUserStore()
const resumeStore = useResumeStore()
const matchStore = useMatchStore()
const learningStore = useLearningStore()
const router = useRouter()
const route = useRoute()

// ── Page mode: single or batch ──
const pageMode = ref('single')

const resumeUploadRef = ref<InstanceType<typeof ResumeUpload> | null>(null)

const step = ref(0)
const targetPositionName = ref('')
const radarData = ref<RadarItem[]>([])
const radarLoading = ref(false)

// 匹配进度动画相关状态
const matchProgress = ref(0)
const matchProgressTimer = ref<ReturnType<typeof setInterval> | null>(null)
const matchAnimating = ref(false)
const matchAnimSkills = ref<SkillMatchItem[]>([])
const matchAnimComplete = ref(false)

import { PROFICIENCY_MAP } from '@/utils/proficiency'
const stepTitles = ['上传简历', '选择目标岗位', '技能雷达对比', '差距分析报告', '学习路径规划']

// ── Step 0: 上传简历 ──
async function handleUpload(file: File) {
  await resumeStore.parseResume(file)
  if (!resumeStore.result) {
    throw new Error('解析结果为空')
  }
  userStore.setResume(file.name, resumeStore.result.required_skills ?? [])
  await new Promise(resolve => setTimeout(resolve, 600))
  // 展示实际抽取模型：云端（deepseek-chat/generalv3.5）秒级，本地（*-fallback）40-120s+
  const model = resumeStore.result.model_used
  const modelNote = model ? `（${model}）` : ''
  ElMessage.success(`简历解析完成，识别 ${userStore.parsedSkills.length} 项技能${modelNote}`)
  step.value = 1
}

onMounted(async () => {
  await nextTick()
  setAsyncUploader()

  // FLOW-02-S2: 重新匹配跳转 —— 从 LearningCenter 携带 rematch 查询参数
  // 直接跳到差距分析步骤（step 3），使用已有匹配结果
  if (route.query.rematch === '1') {
    if (matchStore.result) {
      targetPositionName.value = (route.query.position as string) || ''
      step.value = 3  // 跳到差距分析报告
      matchStore.fetchHistory()
    } else {
      // ponytail: result 是跨页内存态，直输 URL/刷新后为空 → 提示并停留在 step 0，不再静默卡住
      ElMessage.warning('重新匹配结果已失效（页面刷新或直连链接），请重新诊断')
      step.value = 0
    }
  }
})

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

function handleUploadEvent(file: File) {
  handleUpload(file)
}

// 手动输入技能
const skillInput = ref('')
const manualSkills = ref<string[]>([])

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
  // FLOW-03: store structured skills with default proficiency
  userStore.parsedSkills = manualSkills.value.map(s => ({ skill: s, category: 'hard_skill' as const, proficiency: '熟悉' as const }))
  ElMessage.success('已录入 ' + manualSkills.value.length + ' 项技能')
  // QA 优化: 从岗位详情「匹配诊断」CTA 进入时（?position=），确认技能后直接选中目标岗位
  const qPos = route.query.position as string | undefined
  if (qPos) {
    targetPositionName.value = qPos
    void handlePositionSelect({ position_id: '', name: qPos })
    return
  }
  step.value = 1
}

// ── Step 1: 选岗 ──
async function handlePositionSelect(pos: { position_id: string; name: string }) {
  targetPositionName.value = pos.name
  radarLoading.value = true
  try {
    const skillData = await matchStore.fetchPositionSkills(pos.name)
    const skills: { name: string; name_cn?: string; proficiency: string }[] = skillData?.required_skills ?? []
    if (skills.length === 0) {
      ElMessage.warning('未获取到岗位技能数据，仍可继续但雷达图将为空')
      radarData.value = []
      step.value = 2
      return
    }
    radarData.value = skills.map((s) => ({
      skill: s.name_cn || s.name,  // D8i: 技能中文名优先
      required: PROFICIENCY_MAP[s.proficiency] ?? 0.5,
      user: 0,
    }))
    // FLOW-03: parsedSkills is now ParsedSkill[] with real proficiency
    const userSkillSource = resumeStore.result?.required_skills ?? userStore.parsedSkills
    if (userSkillSource.length) {
      const userSkills = new Map(userSkillSource.map((s: { skill: string; proficiency: string }) => [s.skill, PROFICIENCY_MAP[s.proficiency] ?? 0.5]))
      radarData.value = radarData.value.map(item => ({ ...item, user: userSkills.get(item.skill) ?? 0 }))
    }
    step.value = 2
  } catch (e: unknown) {
    ElMessage.warning(`岗位技能请求失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    radarLoading.value = false
  }
}

// ── Step 2: 开始诊断 ──
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
    // FLOW-03: extract skill names from structured parsedSkills
    const skillNames = userStore.parsedSkills.map(s => s.skill)
    const profMap: Record<string, string> = {}
    // Prefer resumeStore proficiency, fallback to parsedSkills proficiency
    if (resumeStore.result?.required_skills) {
      for (const s of resumeStore.result.required_skills) {
        profMap[s.skill] = s.proficiency ?? '熟悉'
      }
    } else {
      for (const s of userStore.parsedSkills) {
        profMap[s.skill] = s.proficiency
      }
    }
    await matchStore.runMatch(targetPositionName.value, skillNames, profMap)
    matchProgress.value = 100

    const result = matchStore.result
    if (result) {
      const matchedSet = new Set(result.matched_skills ?? [])
      const allSkills = [
        ...skillNames.map((s: string) => ({
          name: s,
          matched: matchedSet.has(s),
          // PLAN-006③ 红线: 后端无 match_score 时不再编造 0.85;
          // SkillMatchAnimation 对 score===undefined 会隐藏百分比展示
          score: matchedSet.has(s) ? result.match_score : 0,
        })),
      ]
      for (const g of (result.skill_gap_detail ?? [])) {
        // ponytail: 后端 gap_detail 含"已掌握"条目（语义匹配成功），
        // 若仅按"不在用户输入里"判定，会把已掌握技能误标为未匹配
        if (!skillNames.includes(g.skill) && !matchedSet.has(g.skill)) {
          allSkills.push({ name: g.skill, matched: false, score: 0 })
        }
      }
      matchAnimSkills.value = allSkills
    }

    // / BUG-006: don't advance to step 3 (gap analysis) when
    // the match result is empty — that would leave the wizard stuck on
    // a blank GapAnalysisReport with no recovery path. Stay on step 2,
    // show a warning, and let the user retry with a different position.
    if (!result || (result.matched_skills?.length === 0 && (result.skill_gap_detail?.length ?? 0) === 0)) {
      ElMessage.warning('诊断未产生结果，请检查简历技能或尝试其他岗位')
      matchAnimating.value = false
      matchAnimComplete.value = false
      return
    }

    step.value = 3
  } catch (e: unknown) {
    ElMessage.error('诊断请求失败: ' + (e instanceof Error ? e.message : '未知错误'))
    matchAnimating.value = false
    matchAnimComplete.value = false
    matchProgress.value = 0
    // P0 fix: clear stale result on failure so step 3/4 don't render with null
    matchStore.clearResult()
  } finally {
    if (matchProgressTimer.value) {
      clearInterval(matchProgressTimer.value)
      matchProgressTimer.value = null
    }
  }
}

// ── Step 3/4: computed for sub-components ──
const gapSkills = computed(() => matchStore.result?.skill_gap_detail ?? [])

function goBack() {
  if (step.value > 0) step.value--
}
function goToLearning() {
  step.value = 4
}
function resetAll() {
  step.value = 0
  targetPositionName.value = ''
  radarData.value = []
  matchStore.clearResult()
  matchProgress.value = 0
  manualSkills.value = []
  userStore.clearResume()
}

// MatchFlow navigation handler — jumps the wizard to the
// step associated with the business concept the user clicked.
function onFlowNavigate(targetStep: number) {
  step.value = targetStep
  // Reset transient state that wouldn't make sense when jumping
  // backwards / forwards across the wizard.
  if (targetStep === 0) {
    userStore.clearResume()
    manualSkills.value = []
  }
}

// LOOP-04: 创建学习计划并跳转学习中心
async function handleCreatePlan() {
  if (!matchStore.result) {
    ElMessage.warning('暂无匹配结果，无法创建学习计划')
    return
  }
  try {
    const plan = await learningStore.createPlan(matchStore.result as unknown as Record<string, unknown>)
    if (plan) {
      ElMessage.success('学习计划已创建')
      router.push('/learning')
    }
  } catch (e: unknown) {
    ElMessage.error('创建学习计划失败: ' + (e instanceof Error ? e.message : '未知错误'))
  }
}

onUnmounted(() => {
  if (matchProgressTimer.value) clearInterval(matchProgressTimer.value)
})
</script>

<template>
  <MainLayout>
    <div class="match-page animate-fade-in">
      <div class="page-header">
        <h1 class="page-title">
          匹配诊断
        </h1>
        <p class="page-desc">
          上传简历或输入技能，诊断与目标岗位的匹配度
        </p>
      </div>

      <BusinessBanner
        type="info"
        title="人岗匹配度诊断与差距分析"
        description="上传一份简历，约 30–90 秒得到与目标岗位的匹配度、缺失技能清单和学习路径。结果同时考虑技能命中率和技能在岗位画像中的信任度。"
        :meta="[
          { category: '后端', label: '/match/*', code: true, copyable: true },
          { label: '信任度驱动' },
          { label: '通胀指数参考' },
        ]"
        collapsible
      />

      <!-- 业务流程图 — 让新用户秒懂 6 步骤数据流 -->
      <el-card
        shadow="never"
        class="flow-card"
      >
        <template #header>
          <h3 class="flow-title">
            匹配诊断业务流
          </h3>
        </template>
        <MatchFlow @navigate="onFlowNavigate" />
      </el-card>

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

      <template v-if="pageMode === 'single'">
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
                  <ResumeUpload
                    ref="resumeUploadRef"
                    @upload="handleUploadEvent"
                  />
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
              <!-- D-04: 雷达映射口径注记 — 用户知道对比含模糊匹配 -->
              <p class="radar-note">
                技能对比以精确匹配为主，并含后端归一化与语义模糊匹配补充（雷达上可能显示近似技能名）。
              </p>
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

        <!-- Step 3: Gap analysis report (extracted) -->
        <div v-if="step === 3">
          <!-- 信任度解读 + 质量说明 -->
          <!-- D6 fix: trust_score now reads from the real backend field
               (matched_skills' minimum Neo4j Skill.trust_score). Previously
               this was bound to match_score, displaying the same number twice -->
          <MatchTrustGuide
            :match-score="matchStore.result?.match_score"
            :trust-score="matchStore.result?.trust_score"
            :score-breakdown="matchStore.result?.score_breakdown"
            :note="matchStore.result?.note"
            class="mb-4"
          />
          <GapAnalysisReport
            :target-position="targetPositionName"
            @go-learning="goToLearning"
            @go-back="goBack"
          />
        </div>

        <!-- Step 4: Learning path (extracted) -->
        <LearningPathPlan
          v-if="step === 4"
          :gap-skills="gapSkills"
          @go-back="goBack"
          @reset-all="resetAll"
          @create-plan="handleCreatePlan"
        />
      </template>

      <!-- Batch Match -->
      <MatchBatchMode v-if="pageMode === 'batch'" />
    </div>
  </MainLayout>
</template>

<style scoped>
.match-page {
  max-width: 960px;
  margin: 0 auto;
}

/* ── 业务说明横幅 + 流程图 ── */
.tab-description {
  margin-bottom: var(--space-4);
  border-radius: var(--radius-lg);
}
.tab-description :deep(p) {
  margin: 4px 0 0;
  font-size: var(--font-size-sm);
  color: var(--foreground);
  line-height: 1.5;
}
.tab-description .tab-meta {
  margin-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
.tab-description code {
  background: var(--muted);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 11px;
}

.flow-card {
  margin-bottom: var(--space-4);
  border-radius: var(--radius-xl);
}
.flow-title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 700;
  color: var(--foreground);
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
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary), var(--chart-2));
  opacity: 0.8;
}
.sc-header { margin-bottom: var(--space-6); }
.sc-header-row { display: flex; justify-content: space-between; align-items: flex-start; }
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
.input-section { display: flex; flex-direction: column; gap: var(--space-3); }
.is-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
}
.manual-input { display: flex; flex-direction: column; gap: var(--space-3); }
.skill-tags { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.step-actions { display: flex; gap: var(--space-3); justify-content: center; margin-top: var(--space-6); }
.skill-confirm-action { margin-top: var(--space-4); }

/* D-04: 雷达口径注记 */
.radar-note {
  font-size: 12px;
  color: var(--muted-foreground);
  margin: var(--space-3) 0 0;
  text-align: center;
}

/* Mode Tabs */
.mode-tabs { margin-bottom: var(--space-5); }
.mode-tabs :deep(.el-tabs__header) { margin-bottom: 0; }

/* Match Animation Section */
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
