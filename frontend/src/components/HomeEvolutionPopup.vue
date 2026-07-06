<script setup lang="ts">
import { computed } from 'vue'
import { Close } from '@element-plus/icons-vue'

export interface EvolutionEdgeDetail {
  source: string
  target: string
  type: string
  properties: {
    weight: number
    trend?: 'rising' | 'stable' | 'declining'
    skill_overlap?: string[]
    key_gaps?: string[]
    similarity?: number
    evidence_count?: number
  }
}

const props = defineProps<{
  edge: EvolutionEdgeDetail | null
}>()

const emit = defineEmits<{
  close: []
}>()

const trendLabel = computed(() => {
  const t = props.edge?.properties.trend
  if (t === 'rising') return '↑ 上升'
  if (t === 'declining') return '↓ 下降'
  return '→ 平稳'
})

const trendTagType = computed(() => {
  const t = props.edge?.properties.trend
  if (t === 'rising') return 'success'
  if (t === 'declining') return 'danger'
  return 'info'
})
</script>

<template>
  <Transition name="evolution-popup">
    <div
      v-if="edge"
      class="evolution-detail-popup"
    >
      <div class="edp-header">
        <span class="edp-title">演化路径详情</span>
        <button
          class="edp-close"
          @click="emit('close')"
        >
          <el-icon><Close /></el-icon>
        </button>
      </div>
      <div class="edp-body">
        <div class="edp-row">
          <span class="edp-label">源岗位</span>
          <span class="edp-value">{{ edge.source }}</span>
        </div>
        <div class="edp-row">
          <span class="edp-label">目标岗位</span>
          <span class="edp-value">{{ edge.target }}</span>
        </div>
        <div class="edp-row">
          <span class="edp-label">趋势</span>
          <el-tag
            :type="trendTagType"
            size="small"
            effect="dark"
          >
            {{ trendLabel }}
          </el-tag>
        </div>
        <div class="edp-row">
          <span class="edp-label">相似度</span>
          <span class="edp-value">{{ Math.round((edge.properties.similarity ?? 0) * 100) }}%</span>
        </div>
        <div
          v-if="edge.properties.evidence_count"
          class="edp-row"
        >
          <span class="edp-label">证据数</span>
          <span class="edp-value">{{ edge.properties.evidence_count }}</span>
        </div>
        <div
          v-if="edge.properties.skill_overlap?.length"
          class="edp-section"
        >
          <span class="edp-section-title">重叠技能</span>
          <div class="edp-tags">
            <el-tag
              v-for="s in edge.properties.skill_overlap.slice(0, 8)"
              :key="s"
              size="small"
              type="success"
            >
              {{ s }}
            </el-tag>
          </div>
        </div>
        <div
          v-if="edge.properties.key_gaps?.length"
          class="edp-section"
        >
          <span class="edp-section-title">关键差距</span>
          <div class="edp-tags">
            <el-tag
              v-for="s in edge.properties.key_gaps.slice(0, 8)"
              :key="s"
              size="small"
              type="danger"
            >
              {{ s }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* ── Evolution Edge Detail Popup ── */
.evolution-detail-popup {
  position: absolute;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: var(--space-4) var(--space-5);
  box-shadow: var(--shadow-lg);
  z-index: 20;
  min-width: 280px;
  max-width: 380px;
}
.edp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}
.edp-title {
  font-size: var(--font-size-sm);
  font-weight: 700;
  color: var(--foreground);
  letter-spacing: var(--tracking-tight);
}
.edp-close {
  width: 24px;
  height: 24px;
  border: none;
  background: none;
  color: var(--muted-foreground);
  cursor: pointer;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast);
}
.edp-close:hover { color: var(--destructive); background: var(--destructive-ghost); }
.edp-body { display: flex; flex-direction: column; gap: var(--space-2); }
.edp-row { display: flex; align-items: center; justify-content: space-between; font-size: var(--font-size-sm); }
.edp-label { color: var(--muted-foreground); font-weight: 500; min-width: 60px; }
.edp-value { color: var(--foreground); font-weight: 600; text-align: right; }
.edp-section { margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--border); }
.edp-section-title { font-size: 10px; font-weight: 600; color: var(--muted-foreground); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: var(--space-1-5); display: block; }
.edp-tags { display: flex; flex-wrap: wrap; gap: var(--space-1); }

/* ── Evolution Popup Transition ── */
.evolution-popup-enter-active { transition: all 0.3s var(--ease-out); }
.evolution-popup-leave-active { transition: all 0.2s var(--ease-out); }
.evolution-popup-enter-from { opacity: 0; transform: translateX(-50%) translateY(20px); }
.evolution-popup-leave-to { opacity: 0; transform: translateX(-50%) translateY(10px); }
</style>
