<script setup lang="ts">
/**
 * 学习路径规划 — Step 4 子组件
 * 基于技能差距生成个性化学习路径和时间线
 */
import { computed } from 'vue'
import { RefreshRight } from '@element-plus/icons-vue'
import type { SkillGap } from '@/stores/match'

const props = defineProps<{
  gapSkills: SkillGap[]
}>()

const emit = defineEmits<{
  goBack: []
  resetAll: []
}>()

const learningPaths = computed(() => {
  return props.gapSkills.map(g => {
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
</script>

<template>
  <div class="step-content">
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
            @click="emit('goBack')"
          >
            ← 返回
          </el-button>
        </div>
      </div>

      <!-- 统计摘要 -->
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

      <!-- 学习路径时间线 -->
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
          @click="emit('resetAll')"
        >
          重新开始
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
.step-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
  margin-top: var(--space-6);
}

/* Learning Path Summary */
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

/* Learning Path Timeline */
.lp-timeline { padding: var(--space-2) 0; }
.lp-item {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: var(--space-4) var(--space-5);
  transition: box-shadow 0.2s;
}
.lp-item:hover { box-shadow: var(--shadow-md); }
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
.lp-item-tag { flex-shrink: 0; }
.lp-item-steps { padding-left: calc(1.5em + var(--space-2)); }
.lp-item-steps :deep(.el-step__title) { font-size: var(--font-size-xs); line-height: 1.4; }
.lp-item-steps :deep(.el-step__head) { padding-right: 6px; }
.lp-steps--compact :deep(.el-step) { flex-basis: auto !important; }
.lp-steps--dense :deep(.el-step__title) { font-size: 10px; }
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
.lp-path-empty { opacity: 0.7; }
.lp-path-empty .lp-path-label { font-style: italic; }
</style>
