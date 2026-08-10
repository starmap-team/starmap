<script setup lang="ts">
/**
 * LoopStepInput — Step 1: JD Input
 * Textarea, example JD buttons, target position input, and run button.
 *
 * QA P1-A: target_position is treated as required on the frontend even though
 * the backend now accepts None (see loop_orchestrator._resolve_target_position).
 * The frontend guard fails fast and surfaces the missing field instead of
 * silently submitting a request that the user can no longer contextualize.
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay } from '@element-plus/icons-vue'
import { EXAMPLE_JDS } from '@/constants/demo-jds'

const jdText = defineModel<string>('jdText', { required: true })
const targetPosition = defineModel<string>('targetPosition', { required: true })

defineProps<{
  isRunning: boolean
}>()

const emit = defineEmits<{
  (e: 'run'): void
}>()

const targetPositionError = ref(false)

const exampleJDs = EXAMPLE_JDS

function loadExampleJD(idx: number) {
  const example = exampleJDs[idx]
  jdText.value = example.text
  targetPosition.value = example.position
  targetPositionError.value = false
}

function onRunClick() {
  // Guard: empty JD or empty target_position. Backend now infers position_name
  // from extraction, but we still want the user to declare intent up front —
  // see QA P1-A: backend inference is a fallback, not a UX replacement.
  if (!jdText.value.trim()) {
    ElMessage.warning('请输入 JD 文本')
    return
  }
  if (!targetPosition.value.trim()) {
    targetPositionError.value = true
    ElMessage.warning('请填写目标岗位名称')
    return
  }
  targetPositionError.value = false
  emit('run')
}
</script>

<template>
  <div class="step-section animate-fade-in">
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

      <!-- Target position (required: see QA P1-A / B1) -->
      <el-form-item
        label="目标岗位"
        required
        :error="targetPositionError ? '请填写目标岗位名称' : ''"
      >
        <el-input
          v-model="targetPosition"
          placeholder="目标岗位名称（如：前端工程师）"
          class="target-input"
          clearable
          @input="targetPositionError = false"
        />
      </el-form-item>

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
          :loading="isRunning"
          :disabled="!jdText.trim() || !targetPosition.trim()"
          @click="onRunClick"
        >
          {{ isRunning ? '闭环执行中...' : '开始闭环' }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
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
</style>
