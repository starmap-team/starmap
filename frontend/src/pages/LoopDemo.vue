<script setup lang="ts">
/**
 * 闭环演示页 — THE CORE SHOWCASE PAGE (Refactored)
 * 5 步端到端闭环：JD 输入 → 技能提取 → 图谱更新 → 匹配诊断 → 学习路径
 * 路由：/loop
 *
 * Refactored from 1677 lines into orchestrator + 6 sub-components + 1 composable.
 * - LoopStepInput.vue  — Step 1: JD Input
 * - LoopStepSkills.vue — Step 2: Skill Extraction
 * - LoopStepGraph.vue  — Step 3: Graph Update (uses useLoopGraph)
 * - LoopStepMatch.vue  — Step 4: Match Diagnosis (radar chart + gap analysis)
 * - LoopStepLearning.vue — Step 5: Learning Path
 * - LoopRunLog.vue     — Run Log + History
 * - useLoopGraph.ts    — G6 mini-graph rendering composable
 */
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight, Download } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import LoopTimeline from '@/components/LoopTimeline.vue'
import { useLoopStore } from '@/stores/loop'
import { useLoopGraph } from '@/composables/useLoopGraph'

// Sub-components
import LoopStepInput from '@/components/loop/LoopStepInput.vue'
import LoopStepSkills from '@/components/loop/LoopStepSkills.vue'
import LoopStepGraph from '@/components/loop/LoopStepGraph.vue'
import LoopStepMatch from '@/components/loop/LoopStepMatch.vue'
import LoopStepLearning from '@/components/loop/LoopStepLearning.vue'
import LoopRunLog from '@/components/loop/LoopRunLog.vue'

const loopStore = useLoopStore()
const { graphContainerRef, renderMiniGraph, destroyGraph, extractSkillsFromRun } = useLoopGraph()

// ── Step completion celebration tracking ──
const celebratedSteps = ref<Set<number>>(new Set())

watch(() => loopStore.currentRun?.steps?.map(s => s.status), (statuses) => {
  if (!statuses) return
  statuses.forEach((status, idx) => {
    if (status === 'success' && !celebratedSteps.value.has(idx)) {
      celebratedSteps.value.add(idx)
    }
  })
}, { deep: true })

// ── Step 1 state ──
const jdText = ref('')
const targetPosition = ref('')

// ── Step 4 ref (for buildRadarData) ──
const stepMatchRef = ref<InstanceType<typeof LoopStepMatch> | null>(null)

// ── Run loop ──
async function handleRunLoop() {
  // Defensive guard — LoopStepInput already validates, but a programmatic
  // caller (e.g. test harness) may bypass it. Keep these in sync.
  if (!jdText.value.trim()) {
    ElMessage.warning('请输入 JD 文本')
    return
  }
  if (!targetPosition.value.trim()) {
    ElMessage.warning('请填写目标岗位名称')
    return
  }
  destroyGraph()
  await loopStore.runLoop(jdText.value, targetPosition.value || undefined)

  if (loopStore.error) {
    ElMessage.error(loopStore.error)
  } else {
    ElMessage.success('闭环执行完成')
  }

  // Step 3 完成后渲染 G6 图谱
  await nextTick()
  if (loopStore.currentRun?.steps[2]?.status !== 'waiting') {
    renderMiniGraph(targetPosition.value)
  }
  // Step 4 完成后渲染雷达图
  if (loopStore.currentRun?.steps[3]?.status !== 'waiting') {
    stepMatchRef.value?.buildRadarData()
  }
}

function handleReset() {
  loopStore.resetRun()
  jdText.value = ''
  targetPosition.value = ''
  destroyGraph()
}

// ── Graph ref binding ──
function handleGraphRef(el: HTMLElement | null) {
  graphContainerRef.value = el
}

// ── History ──
onMounted(() => {
  loopStore.fetchHistory()
})

// ── Auto-scroll to results ──
watch(() => loopStore.completedSteps, async () => {
  await nextTick()
  if (loopStore.currentStepIndex >= 2) {
    renderMiniGraph(targetPosition.value)
  }
  if (loopStore.currentStepIndex >= 3) {
    stepMatchRef.value?.buildRadarData()
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

// ── Step visibility helpers ──
// Important: each showStepN must check that currentRun EXISTS first.
// Without the `currentRun != null` guard, `currentRun?.steps[N]?.status`
// evaluates to `undefined` when currentRun is null, and
// `undefined !== 'waiting'` is true — which causes v-if to render the
// step and then crash on `currentRun!.steps[N]` (the non-null assertion
// is unsafe in the template when currentRun is null).
const showStep2 = computed(() => loopStore.currentRun != null && loopStore.currentRun.steps[1]?.status !== 'waiting')
const showStep3 = computed(() => loopStore.currentRun != null && loopStore.currentRun.steps[2]?.status !== 'waiting')
const showStep4 = computed(() => loopStore.currentRun != null && loopStore.currentRun.steps[3]?.status !== 'waiting')
const showStep5 = computed(() => loopStore.currentRun != null && loopStore.currentRun.steps[4]?.status !== 'waiting')
</script>

<template>
  <MainLayout>
    <div class="loop-page animate-fade-in">
      <!-- ── Page Header ── -->
      <div class="starmap-page-header">
        <div>
          <h2 class="starmap-page-title">
            <span class="title-icon">🔄</span>
            闭环验证演示
          </h2>
          <p class="starmap-page-desc">
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

      <!-- ── Step 1: JD Input ── -->
      <LoopStepInput
        v-if="!loopStore.currentRun"
        v-model:jd-text="jdText"
        v-model:target-position="targetPosition"
        :is-running="loopStore.isRunning"
        @run="handleRunLoop"
      />

      <!-- ── Step 2: Skill Extraction ── -->
      <LoopStepSkills
        v-if="showStep2"
        :step="loopStore.currentRun!.steps[1]"
        :celebrated="celebratedSteps.has(1)"
        :skills="extractSkillsFromRun()"
      />

      <!-- ── Step 3: Graph Update ── -->
      <LoopStepGraph
        v-if="showStep3"
        :step="loopStore.currentRun!.steps[2]"
        :celebrated="celebratedSteps.has(2)"
        @graph-ref="handleGraphRef"
      />

      <!-- ── Step 4: Match Diagnosis ── -->
      <LoopStepMatch
        v-if="showStep4"
        ref="stepMatchRef"
        :step="loopStore.currentRun!.steps[3]"
        :celebrated="celebratedSteps.has(3)"
      />

      <!-- ── Step 5: Learning Path ── -->
      <LoopStepLearning
        v-if="showStep5"
        :step="loopStore.currentRun!.steps[4]"
        :celebrated="celebratedSteps.has(4)"
      />

      <!-- ── Run Log + History ── -->
      <LoopRunLog
        :current-run="loopStore.currentRun"
        :history="loopStore.history"
        :total-duration="loopStore.totalDuration"
      />
    </div>
  </MainLayout>
</template>

<style scoped>
.loop-page {
  max-width: 1000px;
  margin: 0 auto;
}

/* ── Page Header ── */
.starmap-page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-6);
}
.starmap-page-title {
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
.starmap-page-desc {
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

/* ── Responsive ── */
@media (max-width: 768px) {
  .starmap-page-header {
    flex-direction: column;
    gap: var(--space-3);
  }
  .header-actions {
    width: 100%;
  }
}
</style>
