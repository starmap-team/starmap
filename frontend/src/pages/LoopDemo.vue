<script setup lang="ts">
/**
 * 闭环演示页 — THE CORE SHOWCASE PAGE
 * 5 步端到端闭环：JD 输入 → 技能提取 → 图谱更新 → 匹配诊断 → 学习路径
 * 路由：/loop
 *
 * 设计要点：
 * - 步骤进度条带动画高亮
 * - 每步结果卡片带淡入动画
 * - Step 3 使用 G6 迷你图谱，新增节点绿色闪烁
 * - Step 4 使用 ECharts 雷达图
 * - 降级步骤黄色警告而非红色
 */
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  VideoPlay, RefreshRight, Document, Download
} from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, RadarComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([RadarChart, TooltipComponent, LegendComponent, RadarComponent, CanvasRenderer])
import MainLayout from '@/layouts/MainLayout.vue'
import LoopTimeline from '@/components/LoopTimeline.vue'
import SkillRadar from '@/components/SkillRadar.vue'
import LoadingPulse from '@/components/LoadingPulse.vue'
import { useLoopStore } from '@/stores/loop'
import { chartColors, legendStyle } from '@/utils/chartTheme'

const loopStore = useLoopStore()

// ── Step completion celebration tracking ──
const celebratedSteps = ref<Set<number>>(new Set())

function celebrateStep(stepIdx: number) {
  if (celebratedSteps.value.has(stepIdx)) return
  celebratedSteps.value.add(stepIdx)
}

// Watch for step completions and trigger celebration
watch(() => loopStore.currentRun?.steps?.map(s => s.status), (statuses) => {
  if (!statuses) return
  statuses.forEach((status, idx) => {
    if (status === 'success' && !celebratedSteps.value.has(idx)) {
      celebrateStep(idx)
    }
  })
}, { deep: true })

// ── G6 动态导入 ──
let G6Graph: any = null
async function ensureG6Loaded() {
  if (!G6Graph) {
    const g6 = await import('@antv/g6')
    G6Graph = g6.Graph
  }
  return G6Graph
}

// ── JD 输入 ──
const jdText = ref('')
const targetPosition = ref('')
const exampleJDs = [
  {
    title: '前端工程师',
    position: '前端工程师',
    text: `岗位职责：
1. 负责公司核心产品的前端开发，使用 Vue3 + TypeScript 技术栈
2. 参与前端架构设计，持续优化前端工程化体系
3. 与后端、设计团队紧密协作，推动产品快速迭代
4. 负责前端性能优化，提升用户体验

任职要求：
1. 计算机相关专业本科及以上学历，3年以上前端开发经验
2. 精通 Vue3、TypeScript、HTML5、CSS3
3. 熟悉 React、Webpack、Vite 等前端工具链
4. 了解 Node.js、Git、CI/CD 流程
5. 具备良好的沟通能力和团队协作精神
6. 有大型 SPA 应用开发经验者优先`,
  },
  {
    title: '数据分析师',
    position: '数据分析师',
    text: `岗位职责：
1. 负责公司数据分析体系建设，搭建数据指标体系
2. 通过数据挖掘和分析，为业务决策提供数据支持
3. 设计和维护数据看板，监控核心业务指标
4. 进行 A/B 测试分析，驱动产品优化

任职要求：
1. 统计学、数学、计算机相关专业本科及以上学历
2. 精通 SQL、Python，熟悉 Pandas、NumPy 等数据分析工具
3. 熟悉 Tableau、Power BI 等数据可视化工具
4. 了解机器学习基本算法（回归、分类、聚类）
5. 具备良好的逻辑思维和数据敏感度
6. 有大数据处理经验（Spark、Hive）者优先`,
  },
  {
    title: 'AI 工程师',
    position: 'AI 工程师',
    text: `岗位职责：
1. 负责大语言模型（LLM）应用的开发与优化
2. 设计和实现 RAG 系统、Prompt Engineering 流程
3. 构建 AI Agent 框架，实现多步骤任务编排
4. 进行模型评估与效果优化，建立质量评估体系

任职要求：
1. 计算机科学、人工智能相关专业硕士及以上学历
2. 精通 Python，熟悉 PyTorch/TensorFlow
3. 熟悉 LangChain、LlamaIndex 等 LLM 应用框架
4. 了解向量数据库（Milvus、Pinecone）、RAG 技术
5. 掌握 NLP 基础技术（Transformer、BERT、GPT）
6. 有 LLM 应用开发或 Agent 系统经验者优先`,
  },
]

function loadExampleJD(idx: number) {
  const example = exampleJDs[idx]
  jdText.value = example.text
  targetPosition.value = example.position
}

// ── 运行闭环 ──
async function handleRunLoop() {
  if (!jdText.value.trim()) {
    ElMessage.warning('请输入 JD 文本')
    return
  }
  graphInstance = null
  await loopStore.runLoop(jdText.value, targetPosition.value || undefined)

  if (loopStore.error) {
    ElMessage.error(loopStore.error)
  } else {
    ElMessage.success('闭环执行完成')
  }

  // Step 3 完成后渲染 G6 图谱
  await nextTick()
  if (loopStore.currentRun?.steps[2]?.status !== 'waiting') {
    renderMiniGraph()
  }
  // Step 4 完成后渲染雷达图
  if (loopStore.currentRun?.steps[3]?.status !== 'waiting') {
    buildRadarData()
  }
}

function handleReset() {
  loopStore.resetRun()
  jdText.value = ''
  targetPosition.value = ''
  radarData.value = []
  if (graphInstance) {
    graphInstance.destroy()
    graphInstance = null
  }
}

// ── Step 3: G6 迷你图谱 ──
const graphContainerRef = ref<HTMLElement | null>(null)
let graphInstance: any = null

function cv(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

async function renderMiniGraph() {
  if (!graphContainerRef.value) return
  const step3Data = loopStore.currentRun?.steps[2]?.data
  if (!step3Data) return

  const GraphClass = await ensureG6Loaded()

  if (graphInstance) {
    graphInstance.destroy()
    graphInstance = null
  }

  const container = graphContainerRef.value
  const width = container.clientWidth || 600
  const height = 320

  graphInstance = new GraphClass({
    container,
    width,
    height,
    layout: {
      type: 'force',
      preventOverlap: true,
      nodeSize: 30,
      nodeSpacing: 20,
      animate: true,
    },
    node: {
      style: {
        labelFill: cv('--foreground'),
        labelFontSize: 11,
        labelPlacement: 'bottom' as const,
        labelOffsetY: 6,
      },
    },
    edge: {
      style: {
        stroke: cv('--border'),
        lineWidth: 1.5,
        opacity: 0.4,
        endArrow: true,
      },
    },
    behaviors: ['drag-canvas', 'zoom-canvas'],
    plugins: [{
      type: 'tooltip',
      enable: true,
      trigger: 'pointerenter',
      offset: [10, 10],
      style: {
        background: cv('--card'),
        borderRadius: '8px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
        padding: '8px 12px',
        fontSize: '12px',
        border: '1px solid ' + cv('--border'),
        color: cv('--foreground'),
      },
    }],
  })

  // Build nodes and edges from step3 data
  const newNodes: any[] = (step3Data.new_nodes ?? []).map((n: any) => ({
    id: n.id ?? n.name,
    style: {
      size: 28,
      fill: '#22c55e',
      fillOpacity: 0.9,
      stroke: '#16a34a',
      lineWidth: 2,
      labelText: n.name ?? n.id,
      labelFill: cv('--foreground'),
      shadowColor: 'rgba(34,197,94,0.4)',
      shadowBlur: 12,
      cursor: 'pointer' as const,
    },
  }))

  const existingNodes: any[] = (step3Data.existing_nodes ?? []).map((n: any) => ({
    id: n.id ?? n.name,
    style: {
      size: 24,
      fill: cv('--primary'),
      fillOpacity: 0.7,
      stroke: cv('--primary'),
      lineWidth: 1.5,
      labelText: n.name ?? n.id,
      labelFill: cv('--foreground'),
      cursor: 'pointer' as const,
    },
  }))

  const allGraphNodes = [...newNodes, ...existingNodes]
  const allGraphEdges: any[] = [
    ...(step3Data.new_edges ?? []).map((e: any) => ({
      id: `${e.source}-${e.target}-new`,
      source: e.source,
      target: e.target,
      style: {
        stroke: '#22c55e',
        lineWidth: 2,
        opacity: 0.7,
        lineDash: [4, 4],
        endArrow: true,
      },
    })),
    ...(step3Data.existing_edges ?? []).map((e: any) => ({
      id: `${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      style: {
        stroke: cv('--border'),
        lineWidth: 1.5,
        opacity: 0.4,
        endArrow: true,
      },
    })),
  ]

  // If no structured data, generate mock visualization
  if (allGraphNodes.length === 0) {
    const skills = extractSkillsFromRun()
    skills.forEach((s, i) => {
      allGraphNodes.push({
        id: `skill_${i}`,
        style: {
          size: s.is_new ? 28 : 24,
          fill: s.is_new ? '#22c55e' : cv('--primary'),
          fillOpacity: s.is_new ? 0.9 : 0.7,
          stroke: s.is_new ? '#16a34a' : cv('--primary'),
          lineWidth: s.is_new ? 2 : 1.5,
          labelText: s.skill,
          labelFill: cv('--foreground'),
          shadowColor: s.is_new ? 'rgba(34,197,94,0.4)' : undefined,
          shadowBlur: s.is_new ? 12 : 0,
          cursor: 'pointer' as const,
        },
      })
    })
    // Connect position node to skills
    if (allGraphNodes.length > 0) {
      const posId = 'position_node'
      allGraphNodes.unshift({
        id: posId,
        style: {
          size: 36,
          fill: cv('--info'),
          fillOpacity: 0.85,
          stroke: cv('--info'),
          lineWidth: 2,
          labelText: targetPosition.value || '目标岗位',
          labelFill: cv('--foreground'),
          labelFontSize: 12,
          labelFontWeight: 'bold' as const,
          shadowColor: 'rgba(37,99,235,0.3)',
          shadowBlur: 12,
          cursor: 'pointer' as const,
        },
      })
      for (let i = 0; i < allGraphNodes.length; i++) {
        if (allGraphNodes[i].id !== posId) {
          allGraphEdges.push({
            id: `${posId}-${allGraphNodes[i].id}`,
            source: posId,
            target: allGraphNodes[i].id,
            style: {
              stroke: cv('--border'),
              lineWidth: 1.5,
              opacity: 0.4,
              endArrow: true,
            },
          })
        }
      }
    }
  }

  if (allGraphNodes.length === 0) return

  // Set initial opacity to 0 for entrance animation
  for (const node of allGraphNodes) {
    node.style.fillOpacity = 0
    node.style.labelOpacity = 0
  }
  graphInstance.setData({ nodes: allGraphNodes, edges: allGraphEdges })
  graphInstance.render()

  // Staggered node entrance animation
  let enterIdx = 0
  const enterInterval = setInterval(() => {
    if (!graphInstance || enterIdx >= allGraphNodes.length) {
      clearInterval(enterInterval)
      return
    }
    const node = allGraphNodes[enterIdx]
    const isNew = newNodes.some(n => n.id === node.id)
    graphInstance.updateNodeData([{
      id: node.id,
      style: {
        fillOpacity: isNew ? 0.9 : 0.7,
        labelOpacity: 1,
      },
    }])
    graphInstance.draw()
    enterIdx++
  }, 80)

  // Blink animation for new nodes (starts after entrance completes)
  if (newNodes.length > 0) {
    let blinkOn = true
    const blinkInterval = setInterval(() => {
      if (!graphInstance) { clearInterval(blinkInterval); return }
      blinkOn = !blinkOn
      for (const n of newNodes) {
        graphInstance.updateNodeData([{
          id: n.id,
          style: {
            fillOpacity: blinkOn ? 0.9 : 0.4,
            shadowBlur: blinkOn ? 16 : 4,
          },
        }])
      }
      graphInstance.draw()
    }, 800)
  }
}

function extractSkillsFromRun(): { skill: string; is_new: boolean; confidence?: number }[] {
  const step2Data = loopStore.currentRun?.steps[1]?.data
  if (!step2Data) return []
  const skills = step2Data.skills ?? []
  return skills.map((s: any) => ({
    skill: s.skill ?? s.name ?? String(s),
    is_new: s.is_new ?? false,
    confidence: s.confidence,
  }))
}

// ── Step 4: 雷达图数据 ──
const radarData = ref<{ skill: string; required: number; matched: number }[]>([])

function buildRadarData() {
  const step4Data = loopStore.currentRun?.steps[3]?.data
  if (!step4Data) return
  if (step4Data.radar_data && step4Data.radar_data.length > 0) {
    radarData.value = step4Data.radar_data
  } else {
    // Build from matched + missing
    const matched = (step4Data.matched_skills ?? []).map((s: string) => ({ skill: s, required: 0.8, matched: 0.7 + Math.random() * 0.25 }))
    const missing = (step4Data.missing_skills ?? []).map((s: string) => ({ skill: s, required: 0.7, matched: Math.random() * 0.3 }))
    radarData.value = [...matched, ...missing].slice(0, 8)
  }
}

const radarOption = computed(() => {
  if (radarData.value.length < 3) return {}
  const colors = chartColors()
  const indicators = radarData.value.map(d => ({ name: d.skill, max: 1 }))
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: legendStyle() },
    radar: {
      center: ['50%', '46%'],
      radius: '62%',
      indicator: indicators,
      axisName: { color: colors.muted, fontSize: 11 },
    },
    series: [{
      type: 'radar',
      name: '岗位要求',
      data: [{ value: radarData.value.map(d => d.required), name: '岗位要求' }],
      lineStyle: { color: colors.danger, width: 2 },
      areaStyle: { color: colors.danger + '33' },
      itemStyle: { color: colors.danger },
    }, {
      type: 'radar',
      name: '匹配程度',
      data: [{ value: radarData.value.map(d => d.matched), name: '匹配程度' }],
      lineStyle: { color: colors.primary, width: 2 },
      areaStyle: { color: colors.primary + '33' },
      itemStyle: { color: colors.primary },
    }],
  }
})

// ── Step 5: 学习路径 ──
const learningPaths = computed(() => {
  const step5Data = loopStore.currentRun?.steps[4]?.data
  if (!step5Data) return []
  return step5Data.paths ?? step5Data.learning_paths ?? []
})

// ── Run log ──
const runLog = computed(() => {
  if (!loopStore.currentRun) return []
  const log: { time: string; message: string; type: string }[] = []
  for (const step of loopStore.currentRun.steps) {
    if (step.status === 'success') {
      log.push({ time: formatDuration(step.duration_ms), message: `✓ Step ${step.step}: ${step.name} 完成`, type: 'success' })
    } else if (step.status === 'degraded') {
      log.push({ time: formatDuration(step.duration_ms), message: `⚠ Step ${step.step}: ${step.name} 降级 — ${step.warning ?? '部分数据不可用'}`, type: 'warning' })
    } else if (step.status === 'failed') {
      log.push({ time: '', message: `✕ Step ${step.step}: ${step.name} 失败 — ${step.error ?? '未知错误'}`, type: 'error' })
    } else if (step.status === 'running') {
      log.push({ time: '', message: `⟳ Step ${step.step}: ${step.name} 执行中...`, type: 'info' })
    }
  }
  return log
})

function formatDuration(ms?: number): string {
  if (!ms) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

// ── History ──
onMounted(() => {
  loopStore.fetchHistory()
})

// ── Auto-scroll to results ──
watch(() => loopStore.completedSteps, async () => {
  await nextTick()
  if (loopStore.currentStepIndex >= 2) {
    renderMiniGraph()
  }
  if (loopStore.currentStepIndex >= 3) {
    buildRadarData()
  }
})

// ── Export report ──
function exportReport() {
  if (!loopStore.currentRun) return
  const report = {
    run_id: loopStore.currentRun.run_id,
    target_position: loopStore.currentRun.target_position,
    steps: loopStore.currentRun.steps.map(s => ({
      step: s.step,
      name: s.name,
      status: s.status,
      duration_ms: s.duration_ms,
      data: s.data,
    })),
    total_duration_ms: loopStore.totalDuration,
    exported_at: new Date().toISOString(),
  }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `loop-report-${loopStore.currentRun.run_id}.json`; a.click()
  URL.revokeObjectURL(url)
}

// ── Cleanup ──
onUnmounted(() => {
  if (graphInstance) {
    graphInstance.destroy()
    graphInstance = null
  }
})
</script>

<template>
  <MainLayout>
    <div class="loop-page animate-fade-in">
      <!-- ── Page Header ── -->
      <div class="page-header">
        <div class="page-header-content">
          <h1 class="page-title">
            <span class="title-icon">🔄</span>
            闭环验证演示
          </h1>
          <p class="page-desc">
            端到端 AI 知识图谱闭环：输入 JD → 技能提取 → 图谱更新 → 匹配诊断 → 学习路径
          </p>
        </div>
        <div
          v-if="loopStore.currentRun"
          class="header-actions"
        >
          <el-button
            :icon="Download"
            size="small"
            @click="exportReport"
          >
            导出报告
          </el-button>
          <el-button
            :icon="RefreshRight"
            size="small"
            @click="handleReset"
          >
            重新开始
          </el-button>
        </div>
      </div>

      <!-- ── Timeline ── -->
      <el-card
        v-if="loopStore.currentRun"
        shadow="never"
        class="timeline-card"
      >
        <LoopTimeline
          :steps="loopStore.currentRun.steps"
          :active-step="loopStore.currentStepIndex"
          @step-click="(idx) => {}"
        />
      </el-card>

      <!-- ═══════════════════════════════════════════════════ -->
      <!-- Step 1: JD 输入 -->
      <!-- ═══════════════════════════════════════════════════ -->
      <div
        v-if="!loopStore.currentRun"
        class="step-section animate-fade-in"
      >
        <el-card
          shadow="never"
          class="step-card"
        >
          <template #header>
            <div class="sc-header">
              <div>
                <h2 class="sc-title">
                  <span class="step-num">1</span>
                  JD 文本输入
                </h2>
                <p class="sc-desc">
                  粘贴职位描述文本，或选择示例 JD 快速体验
                </p>
              </div>
            </div>
          </template>

          <!-- 示例 JD 按钮组 -->
          <div class="example-jd-group">
            <span class="example-label">示例 JD：</span>
            <el-button
              v-for="(ex, idx) in exampleJDs"
              :key="idx"
              size="small"
              plain
              @click="loadExampleJD(idx)"
            >
              {{ ex.title }}
            </el-button>
          </div>

          <!-- Target position -->
          <el-input
            v-model="targetPosition"
            placeholder="目标岗位名称（可选，如：前端工程师）"
            class="target-input"
            clearable
          >
            <template #prepend>
              目标岗位
            </template>
          </el-input>

          <!-- JD textarea -->
          <el-input
            v-model="jdText"
            type="textarea"
            :rows="12"
            placeholder="在此粘贴职位描述文本...&#10;&#10;系统将自动：&#10;1. 提取技能要求&#10;2. 更新知识图谱&#10;3. 进行匹配诊断&#10;4. 生成学习路径"
            maxlength="10000"
            show-word-limit
            class="jd-textarea"
          />

          <div class="step-actions">
            <el-button
              type="primary"
              size="large"
              :icon="VideoPlay"
              :loading="loopStore.isRunning"
              :disabled="!jdText.trim()"
              @click="handleRunLoop"
            >
              {{ loopStore.isRunning ? '闭环执行中...' : '开始闭环' }}
            </el-button>
          </div>
        </el-card>
      </div>

      <!-- ═══════════════════════════════════════════════════ -->
      <!-- Step 2: 技能提取结果 -->
      <!-- ═══════════════════════════════════════════════════ -->
      <div
        v-if="loopStore.currentRun?.steps[1]?.status !== 'waiting'"
        class="step-section animate-fade-in"
        :class="{ 'anim-celebrate': celebratedSteps.has(1) }"
      >
        <el-card
          shadow="never"
          class="step-card"
        >
          <template #header>
            <div class="sc-header">
              <h2 class="sc-title">
                <span class="step-num">2</span>
                技能提取结果
              </h2>
              <div
                v-if="loopStore.currentRun?.steps[1]?.data"
                class="sc-metrics"
              >
                <el-tag
                  type="info"
                  size="small"
                  effect="plain"
                >
                  置信度: {{ ((loopStore.currentRun.steps[1].data.confidence ?? 0) * 100).toFixed(0) }}%
                </el-tag>
                <el-tag
                  :type="(loopStore.currentRun.steps[1].data.hallucination_score ?? 0) > 0.3 ? 'warning' : 'success'"
                  size="small"
                  effect="plain"
                >
                  幻觉评分: {{ ((loopStore.currentRun.steps[1].data.hallucination_score ?? 0) * 100).toFixed(0) }}%
                </el-tag>
              </div>
            </div>
          </template>

          <div
            v-if="loopStore.currentRun?.steps[1]?.data"
            class="extracted-skills stagger"
          >
            <div
              v-for="(skill, idx) in extractSkillsFromRun()"
              :key="skill.skill"
              class="skill-chip anim-fade-in-up"
              :class="{ 'skill-new': skill.is_new, 'skill-existing': !skill.is_new }"
              :style="{ animationDelay: (idx * 60) + 'ms' }"
            >
              <span class="chip-marker">{{ skill.is_new ? '🆕' : '✅' }}</span>
              <span class="chip-name">{{ skill.skill }}</span>
              <span
                v-if="skill.confidence"
                class="chip-conf"
              >{{ (skill.confidence * 100).toFixed(0) }}%</span>
            </div>
            <div
              v-if="extractSkillsFromRun().length === 0"
              class="empty-skills"
            >
              暂无提取结果
            </div>
          </div>

          <div
            v-if="loopStore.currentRun?.steps[1]?.status === 'running'"
            v-loading="true"
            style="min-height: 100px"
          />
        </el-card>
      </div>

      <!-- ═══════════════════════════════════════════════════ -->
      <!-- Step 3: 图谱更新 -->
      <!-- ═══════════════════════════════════════════════════ -->
      <div
        v-if="loopStore.currentRun?.steps[2]?.status !== 'waiting'"
        class="step-section animate-fade-in"
        :class="{ 'anim-celebrate': celebratedSteps.has(2) }"
      >
        <el-card
          shadow="never"
          class="step-card"
        >
          <template #header>
            <div class="sc-header">
              <h2 class="sc-title">
                <span class="step-num">3</span>
                图谱更新
              </h2>
              <div
                v-if="loopStore.currentRun?.steps[2]?.warning"
                class="degraded-badge"
              >
                ⚠ {{ loopStore.currentRun.steps[2].warning }}
              </div>
            </div>
          </template>

          <div class="graph-legend">
            <span class="legend-item">
              <span class="legend-dot legend-new" />
              新增节点
            </span>
            <span class="legend-item">
              <span class="legend-dot legend-existing" />
              已有节点
            </span>
            <span class="legend-item">
              <span class="legend-dot legend-edge" />
              关系边
            </span>
          </div>

          <div
            v-if="loopStore.currentRun?.steps[2]?.status === 'running'"
            v-loading="true"
            style="min-height: 320px"
          />
          <div
            v-else
            ref="graphContainerRef"
            class="mini-graph-container"
          />
        </el-card>
      </div>

      <!-- ═══════════════════════════════════════════════════ -->
      <!-- Step 4: 匹配诊断 -->
      <!-- ═══════════════════════════════════════════════════ -->
      <div
        v-if="loopStore.currentRun?.steps[3]?.status !== 'waiting'"
        class="step-section animate-fade-in"
        :class="{ 'anim-celebrate': celebratedSteps.has(3) }"
      >
        <el-card
          shadow="never"
          class="step-card"
        >
          <template #header>
            <div class="sc-header">
              <h2 class="sc-title">
                <span class="step-num">4</span>
                匹配诊断
              </h2>
              <div
                v-if="loopStore.currentRun?.steps[3]?.data?.match_score !== undefined"
                class="match-score-badge"
              >
                <span class="score-value">{{ Math.round((loopStore.currentRun.steps[3].data.match_score ?? 0) * 100) }}</span>
                <span class="score-unit">%</span>
              </div>
            </div>
          </template>

          <div
            v-if="loopStore.currentRun?.steps[3]?.status === 'running'"
            v-loading="true"
            style="min-height: 200px"
          />

          <div v-else-if="loopStore.currentRun?.steps[3]?.data">
            <el-row :gutter="20">
              <!-- Radar chart -->
              <el-col
                :span="12"
                :xs="24"
              >
                <div
                  v-if="radarData.length >= 3"
                  class="radar-container"
                >
                  <VChart
                    :option="radarOption"
                    style="height: 340px"
                    autoresize
                  />
                </div>
                <div
                  v-else
                  class="radar-empty"
                >
                  雷达图数据不足
                </div>
              </el-col>

              <!-- Gap analysis -->
              <el-col
                :span="12"
                :xs="24"
              >
                <div class="gap-analysis">
                  <!-- Matched skills -->
                  <h4 class="gap-section-title">
                    ✓ 匹配技能
                  </h4>
                  <div class="skill-tags-row">
                    <el-tag
                      v-for="s in (loopStore.currentRun.steps[3].data.matched_skills ?? [])"
                      :key="s"
                      type="success"
                      size="small"
                      effect="plain"
                    >
                      {{ s }}
                    </el-tag>
                    <span
                      v-if="!(loopStore.currentRun.steps[3].data.matched_skills?.length)"
                      class="empty-text"
                    >无</span>
                  </div>

                  <!-- Missing skills -->
                  <h4 class="gap-section-title">
                    ✕ 缺失技能
                  </h4>
                  <div class="skill-tags-row">
                    <el-tag
                      v-for="s in (loopStore.currentRun.steps[3].data.missing_skills ?? loopStore.currentRun.steps[3].data.gap_analysis?.map((g: any) => g.skill) ?? [])"
                      :key="s"
                      type="danger"
                      size="small"
                      effect="plain"
                    >
                      {{ s }}
                    </el-tag>
                    <span
                      v-if="!(loopStore.currentRun.steps[3].data.missing_skills?.length) && !(loopStore.currentRun.steps[3].data.gap_analysis?.length)"
                      class="empty-text"
                    >无</span>
                  </div>

                  <!-- Gap detail table -->
                  <div
                    v-if="loopStore.currentRun.steps[3].data.gap_analysis?.length"
                    class="gap-table-wrapper"
                  >
                    <h4 class="gap-section-title">
                      差距明细
                    </h4>
                    <el-table
                      :data="loopStore.currentRun.steps[3].data.gap_analysis"
                      size="small"
                      stripe
                      max-height="200"
                    >
                      <el-table-column
                        prop="skill"
                        label="技能"
                        min-width="100"
                      />
                      <el-table-column
                        label="重要性"
                        width="80"
                        align="center"
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
                        width="90"
                        align="center"
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
                    </el-table>
                  </div>
                </div>
              </el-col>
            </el-row>
          </div>
        </el-card>
      </div>

      <!-- ═══════════════════════════════════════════════════ -->
      <!-- Step 5: 学习路径 -->
      <!-- ═══════════════════════════════════════════════════ -->
      <div
        v-if="loopStore.currentRun?.steps[4]?.status !== 'waiting'"
        class="step-section animate-fade-in"
        :class="{ 'anim-celebrate': celebratedSteps.has(4) }"
      >
        <el-card
          shadow="never"
          class="step-card"
        >
          <template #header>
            <div class="sc-header">
              <h2 class="sc-title">
                <span class="step-num">5</span>
                学习路径
              </h2>
              <div
                v-if="loopStore.currentRun?.steps[4]?.data?.estimated_total_hours"
                class="est-time-badge"
              >
                预计 {{ loopStore.currentRun.steps[4].data.estimated_total_hours }}h
              </div>
            </div>
          </template>

          <div
            v-if="loopStore.currentRun?.steps[4]?.status === 'running'"
            v-loading="true"
            style="min-height: 100px"
          />

          <div v-else-if="learningPaths.length > 0">
            <!-- Learning path flow -->
            <div class="path-flow stagger">
              <div
                v-for="(item, idx) in learningPaths"
                :key="idx"
                class="path-item anim-fade-in-up"
                :style="{ animationDelay: (idx * 80) + 'ms' }"
              >
                <div class="path-num">
                  {{ idx + 1 }}
                </div>
                <div class="path-info">
                  <div class="path-skill-name">
                    {{ item.skill ?? item.name ?? item }}
                  </div>
                  <div
                    v-if="item.estimated_hours || item.hours"
                    class="path-hours"
                  >
                    ≈ {{ item.estimated_hours ?? item.hours }}h
                  </div>
                  <div
                    v-if="item.prerequisites?.length"
                    class="path-prereq"
                  >
                    前置: {{ item.prerequisites.join(', ') }}
                  </div>
                </div>
                <div
                  v-if="idx < learningPaths.length - 1"
                  class="path-arrow"
                >
                  →
                </div>
              </div>
            </div>

            <!-- Prerequisite graph (simple visual) -->
            <div
              v-if="learningPaths.some((p: any) => p.prerequisites?.length)"
              class="prereq-section"
            >
              <h4 class="gap-section-title">
                前置条件关系
              </h4>
              <div class="prereq-list">
                <div
                  v-for="(item, idx) in learningPaths.filter((p: any) => p.prerequisites?.length)"
                  :key="idx"
                  class="prereq-item"
                >
                  <span class="prereq-arrow">{{ item.prerequisites.join(' + ') }}</span>
                  <span class="prereq-arrow-icon">→</span>
                  <span class="prereq-target">{{ item.skill ?? item.name }}</span>
                </div>
              </div>
            </div>
          </div>

          <div
            v-else
            class="empty-paths"
          >
            暂无学习路径数据
          </div>
        </el-card>
      </div>

      <!-- ═══════════════════════════════════════════════════ -->
      <!-- Run Log + Duration Stats -->
      <!-- ═══════════════════════════════════════════════════ -->
      <div
        v-if="loopStore.currentRun && runLog.length > 0"
        class="step-section animate-fade-in"
      >
        <el-card
          shadow="never"
          class="step-card run-log-card"
        >
          <template #header>
            <div class="sc-header">
              <h2 class="sc-title">
                运行日志
              </h2>
              <div class="total-duration">
                总耗时: <strong>{{ formatDuration(loopStore.totalDuration) }}</strong>
              </div>
            </div>
          </template>

          <div class="log-entries">
            <div
              v-for="(entry, idx) in runLog"
              :key="idx"
              class="log-entry"
              :class="`log-${entry.type}`"
            >
              <span class="log-message">{{ entry.message }}</span>
              <span
                v-if="entry.time"
                class="log-time"
              >{{ entry.time }}</span>
            </div>
          </div>

          <!-- Duration bar chart (simple) -->
          <div class="duration-bars">
            <div
              v-for="step in loopStore.currentRun.steps"
              :key="step.step"
              class="dur-bar-row"
            >
              <span class="dur-label">Step {{ step.step }}</span>
              <div class="dur-bar-track">
                <div
                  class="dur-bar-fill"
                  :class="`dur-${step.status}`"
                  :style="{ width: step.duration_ms ? `${Math.max(5, (step.duration_ms / (loopStore.totalDuration || 1)) * 100)}%` : '0%' }"
                />
              </div>
              <span class="dur-value">{{ formatDuration(step.duration_ms) }}</span>
            </div>
          </div>
        </el-card>
      </div>

      <!-- ═══════════════════════════════════════════════════ -->
      <!-- History -->
      <!-- ═══════════════════════════════════════════════════ -->
      <div
        v-if="loopStore.history.length > 0 && !loopStore.currentRun"
        class="step-section animate-fade-in"
      >
        <el-card
          shadow="never"
          class="step-card"
        >
          <template #header>
            <h2 class="sc-title">
              历史记录
            </h2>
          </template>
          <el-table
            :data="loopStore.history"
            stripe
            size="small"
          >
            <el-table-column
              prop="run_id"
              label="运行 ID"
              min-width="160"
            />
            <el-table-column
              prop="target_position"
              label="目标岗位"
              min-width="120"
            />
            <el-table-column
              label="状态"
              width="90"
              align="center"
            >
              <template #default="{ row }">
                <el-tag
                  :type="row.status === 'completed' ? 'success' : row.status === 'partial' ? 'warning' : 'info'"
                  size="small"
                >
                  {{ row.status === 'completed' ? '完成' : row.status === 'partial' ? '部分' : row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="步骤"
              width="80"
              align="center"
            >
              <template #default="{ row }">
                {{ row.success_count }}/{{ row.step_count }}
              </template>
            </el-table-column>
            <el-table-column
              label="耗时"
              width="90"
              align="center"
            >
              <template #default="{ row }">
                {{ formatDuration(row.total_duration_ms) }}
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
        </el-card>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.loop-page {
  max-width: 1000px;
  margin: 0 auto;
}

/* ── Page Header ── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-6);
}
.page-header-content {
  flex: 1;
}
.page-title {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.title-icon {
  font-size: 1.1em;
}
.page-desc {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
  line-height: var(--leading-relaxed);
}
.header-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

/* ── Timeline Card ── */
.timeline-card {
  margin-bottom: var(--space-5);
  border-radius: var(--radius-2xl);
  overflow: hidden;
}

/* ── Step Section ── */
.step-section {
  margin-bottom: var(--space-5);
  animation: fade-in-up 0.4s var(--ease-out);
}
@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Step Card ── */
.step-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-2xl);
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
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sc-title {
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--chart-2));
  color: white;
  font-size: var(--font-size-sm);
  font-weight: 700;
  flex-shrink: 0;
}
.sc-desc {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}
.sc-metrics {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

/* ── Step 1: JD Input ── */
.example-jd-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}
.example-label {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  font-weight: 500;
}
.target-input {
  margin-bottom: var(--space-3);
}
.jd-textarea {
  margin-bottom: var(--space-3);
}
.step-actions {
  display: flex;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

/* ── Step 2: Extracted Skills ── */
.extracted-skills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-2) 0;
}
.skill-chip {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--font-size-sm);
  font-weight: 500;
  transition: all 0.3s var(--ease-out);
}
.skill-new {
  background: color-mix(in srgb, #22c55e 12%, var(--card));
  border: 1px solid color-mix(in srgb, #22c55e 30%, var(--border));
  color: #16a34a;
}
.skill-existing {
  background: color-mix(in srgb, var(--primary) 8%, var(--card));
  border: 1px solid color-mix(in srgb, var(--primary) 20%, var(--border));
  color: var(--primary);
}
.chip-marker {
  font-size: 12px;
}
.chip-conf {
  font-size: 11px;
  opacity: 0.7;
  font-variant-numeric: tabular-nums;
}
.empty-skills {
  text-align: center;
  padding: var(--space-6);
  color: var(--muted-foreground);
}

/* ── Step 3: Graph ── */
.graph-legend {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-3);
  justify-content: center;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.legend-new {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}
.legend-existing {
  background: var(--primary);
}
.legend-edge {
  background: var(--border);
  border-radius: 2px;
  height: 2px;
  width: 14px;
}
.mini-graph-container {
  width: 100%;
  height: 320px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  overflow: hidden;
  background: color-mix(in srgb, var(--card) 95%, var(--foreground));
}
.degraded-badge {
  font-size: var(--font-size-xs);
  color: var(--warning);
  background: color-mix(in srgb, var(--warning) 10%, var(--card));
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  border: 1px solid color-mix(in srgb, var(--warning) 20%, var(--border));
}

/* ── Step 4: Match Diagnosis ── */
.match-score-badge {
  display: flex;
  align-items: baseline;
}
.score-value {
  font-size: 2rem;
  font-weight: 900;
  background: linear-gradient(135deg, var(--primary), var(--chart-1));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
}
.score-unit {
  font-size: var(--font-size-lg);
  color: var(--muted-foreground);
  margin-left: var(--space-1);
  font-weight: 600;
}
.radar-container {
  padding: var(--space-2);
}
.radar-empty {
  text-align: center;
  padding: var(--space-8);
  color: var(--muted-foreground);
}
.gap-analysis {
  padding: var(--space-2) 0;
}
.gap-section-title {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--muted-foreground);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: var(--space-4) 0 var(--space-2);
}
.gap-section-title:first-child {
  margin-top: 0;
}
.skill-tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
.empty-text {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
}
.gap-table-wrapper {
  margin-top: var(--space-3);
}

/* ── Step 5: Learning Path ── */
.path-flow {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3) 0;
}
.path-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--muted);
  border-radius: var(--radius-lg);
  padding: var(--space-2) var(--space-4);
  transition: transform 0.2s var(--ease-out);
}
.path-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}
.path-num {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--chart-2));
  color: white;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.path-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.path-skill-name {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--foreground);
}
.path-hours {
  font-size: 11px;
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
}
.path-prereq {
  font-size: 11px;
  color: var(--warning);
}
.path-arrow {
  font-size: var(--font-size-lg);
  color: var(--muted-foreground);
  font-weight: 300;
}
.est-time-badge {
  font-size: var(--font-size-sm);
  color: var(--primary);
  font-weight: 600;
  background: color-mix(in srgb, var(--primary) 8%, var(--card));
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
}
.prereq-section {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border);
}
.prereq-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.prereq-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}
.prereq-arrow {
  color: var(--muted-foreground);
}
.prereq-arrow-icon {
  color: var(--primary);
  font-weight: 600;
}
.prereq-target {
  color: var(--foreground);
  font-weight: 600;
}
.empty-paths {
  text-align: center;
  padding: var(--space-6);
  color: var(--muted-foreground);
}

/* ── Run Log ── */
.run-log-card::before {
  background: linear-gradient(90deg, var(--chart-2), var(--chart-1));
}
.total-duration {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
}
.log-entries {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  background: color-mix(in srgb, var(--foreground) 3%, var(--card));
  border-radius: var(--radius-lg);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: var(--font-size-xs);
}
.log-entry {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
}
.log-message {
  color: var(--foreground);
}
.log-time {
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.log-success .log-message { color: var(--success); }
.log-warning .log-message { color: var(--warning); }
.log-error .log-message { color: var(--danger); }
.log-info .log-message { color: var(--primary); }

/* ── Duration Bars ── */
.duration-bars {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.dur-bar-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.dur-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  width: 56px;
  flex-shrink: 0;
  font-weight: 500;
}
.dur-bar-track {
  flex: 1;
  height: 8px;
  background: var(--muted);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.dur-bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.6s var(--ease-out);
  min-width: 4px;
}
.dur-success { background: linear-gradient(90deg, var(--success), #22c55e); }
.dur-degraded { background: linear-gradient(90deg, var(--warning), #f59e0b); }
.dur-failed { background: linear-gradient(90deg, var(--danger), #ef4444); }
.dur-running { background: linear-gradient(90deg, var(--primary), var(--chart-2)); }
.dur-waiting { background: var(--border); }
.dur-value {
  font-size: 11px;
  color: var(--muted-foreground);
  width: 50px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

/* ── Celebration Effect ── */
.anim-celebrate {
  animation: loopCelebrate 0.7s var(--ease-out) both;
}
@keyframes loopCelebrate {
  0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--success) 40%, transparent); }
  50% { box-shadow: 0 0 0 8px color-mix(in srgb, var(--success) 0%, transparent); }
  100% { box-shadow: 0 0 0 0 transparent; }
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: var(--space-3);
  }
  .header-actions {
    width: 100%;
  }
}
</style>
