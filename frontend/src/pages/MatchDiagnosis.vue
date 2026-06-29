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
  Upload, Edit, Search, DataAnalysis, Document,
  ChatDotSquare, Guide, ArrowLeft, Check, RefreshRight,
  Plus, Download
} from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
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
const showManualInput = ref(true) 

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
    <div class="match-page">
      <!-- 顶部步骤条 -->
      <el-steps :active="step" finish-status="success" align-center class="steps-bar">
        <el-step v-for="title in stepTitles" :key="title" :title="title" />
      </el-steps>

      <!-- Step 0: 上传简历 / 手动输入 -->
      <div v-if="step === 0" class="step-content">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Upload /></el-icon>
              <span>上传简历或手动输入技能</span>
            </div>
          </template>
          <ResumeUpload ref="resumeUploadRef" />
          <el-divider>或</el-divider>
          <el-button type="primary" plain @click="showManualInput = !showManualInput">
            <el-icon><Edit /></el-icon>
            手动输入技能
          </el-button>
          <div v-if="showManualInput" class="manual-input-area">
            <el-input
              v-model="skillInput"
              placeholder="输入技能名称后回车添加"
              size="large"
              @keyup.enter="addManualSkill"
            >
              <template #append>
                <el-button @click="addManualSkill"><el-icon><Plus /></el-icon></el-button>
              </template>
            </el-input>
            <div class="skill-tags" v-if="manualSkills.length">
              <el-tag
                v-for="s in manualSkills"
                :key="s"
                closable
                size="large"
                @close="removeManualSkill(s)"
              >{{ s }}</el-tag>
            </div>
            <el-button
              type="success"
              :disabled="!manualSkills.length"
              @click="confirmManualSkills"
              style="margin-top: 12px"
            >
              <el-icon><Check /></el-icon>
              确认 {{ manualSkills.length }} 项技能
            </el-button>
          </div>
        </el-card>
      </div>

      <!-- Step 1: 选岗 -->
      <div v-if="step === 1" class="step-content">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Search /></el-icon>
              <span>选择目标岗位</span>
              <el-button text @click="goBack"><el-icon><ArrowLeft /></el-icon>返回</el-button>
            </div>
          </template>
          <PositionSearch @select="handlePositionSelect" />
          <div v-if="radarLoading" style="text-align:center;margin-top:20px">
            <el-icon class="is-loading" :size="24"><RefreshRight /></el-icon>
            <span style="margin-left:8px">正在加载岗位技能数据...</span>
          </div>
        </el-card>
      </div>

      <!-- Step 2: 雷达图 -->
      <div v-if="step === 2" class="step-content">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><DataAnalysis /></el-icon>
              <span>技能雷达对比 — {{ targetPositionName }}</span>
              <el-button text @click="goBack"><el-icon><ArrowLeft /></el-icon>返回</el-button>
            </div>
          </template>
          <SkillRadar :data="radarData" :position-name="targetPositionName" />
          <div v-if="radarData.length === 0" class="empty-hint">暂无雷达图数据</div>
          <div style="text-align:center;margin-top:20px">
            <el-button type="primary" size="large" @click="handleStartDiagnosis" :loading="matchStore.loading">
              <el-icon><Guide /></el-icon>
              开始诊断
            </el-button>
          </div>
          <!-- 进度条 -->
          <el-progress
            v-if="matchStore.loading"
            :percentage="Math.min(Math.round(matchProgress), 100)"
            :stroke-width="10"
            style="margin-top:16px"
          />
        </el-card>
      </div>

      <!-- Step 3: 差距分析报告 -->
      <div v-if="step === 3" class="step-content">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Document /></el-icon>
              <span>差距分析报告</span>
              <el-button text @click="goBack"><el-icon><ArrowLeft /></el-icon>返回</el-button>
            </div>
          </template>
          <div v-if="matchResult">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="匹配度">
                <el-tag :type="matchScore >= 0.7 ? 'success' : matchScore >= 0.4 ? 'warning' : 'danger'" size="large">
                  {{ (matchScore * 100).toFixed(1) }}%
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="目标岗位">{{ targetPositionName }}</el-descriptions-item>
              <el-descriptions-item label="已匹配技能" :span="2">
                <el-tag v-for="s in matchedSkills" :key="s" type="success" style="margin:2px">{{ s }}</el-tag>
                <span v-if="!matchedSkills.length" style="color:#909399">无</span>
              </el-descriptions-item>
              <el-descriptions-item label="综合评估" :span="2">
                {{ matchResult.overall_assessment ?? '暂无评估' }}
              </el-descriptions-item>
              <el-descriptions-item v-if="matchResult.estimated_learning_time" label="预计学习时间">
                {{ matchResult.estimated_learning_time }}
              </el-descriptions-item>
            </el-descriptions>

            <!-- 技能差距表格 -->
            <h3 style="margin-top:20px">技能差距明细</h3>
            <el-table :data="gapSkills" stripe border style="width:100%">
              <el-table-column prop="skill" label="技能" width="180" />
              <el-table-column prop="importance" label="重要性" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.importance === 'required' ? 'danger' : 'info'" size="small">
                    {{ row.importance === 'required' ? '必备' : '加分' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="gap_level" label="差距程度" width="120">
                <template #default="{ row }">
                  <el-tag :type="row.gap_level === '完全缺失' ? 'danger' : row.gap_level === '部分掌握' ? 'warning' : 'success'" size="small">
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

            <div style="text-align:center;margin-top:20px;display:flex;gap:12px;justify-content:center">
              <el-button type="primary" size="large" @click="goToLearning">
                <el-icon><Guide /></el-icon>
                查看学习路径
              </el-button>
              <el-button size="large" @click="exportReport">
                <el-icon><Download /></el-icon>
                导出报告
              </el-button>
            </div>
          </div>
          <div v-else class="empty-hint">暂无诊断结果</div>
        </el-card>
      </div>

      <!-- Step 4: 学习路径 -->
      <div v-if="step === 4" class="step-content">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><ChatDotSquare /></el-icon>
              <span>学习路径规划</span>
              <el-button text @click="goBack"><el-icon><ArrowLeft /></el-icon>返回</el-button>
            </div>
          </template>
          <el-table :data="learningPaths" stripe border style="width:100%">
            <el-table-column prop="skill" label="技能" width="160" />
            <el-table-column prop="importance" label="优先级" width="100">
              <template #default="{ row }">
                <el-tag :type="row.importance === 'required' ? 'danger' : 'info'" size="small">
                  {{ row.importance === 'required' ? '必备' : '加分' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="gapLevel" label="差距" width="100">
              <template #default="{ row }">
                <el-tag :type="row.gapLevel === '完全缺失' ? 'danger' : 'warning'" size="small">
                  {{ row.gapLevel }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="path" label="推荐学习路径" />
          </el-table>
          <div style="text-align:center;margin-top:20px">
            <el-button size="large" @click="resetAll">
              <el-icon><RefreshRight /></el-icon>
              重新开始
            </el-button>
          </div>
        </el-card>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.match-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}
.steps-bar {
  margin-bottom: 24px;
}
.step-content {
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}
.card-header .el-button {
  margin-left: auto;
}
.manual-input-area {
  margin-top: 16px;
}
.skill-tags {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.empty-hint {
  text-align: center;
  color: #909399;
  padding: 40px 0;
  font-size: 14px;
}
</style>
