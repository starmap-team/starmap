<script setup lang="ts">
/**
 * NodeTooltip3D — floating tooltip for 3D graph nodes
 * Positioned via CSS2DRenderer coordinates; shows node name, type, and key stats.
 */
import { computed } from 'vue'
import { TYPE_INFO } from '@/utils/graphColors'

interface TooltipNode {
  id: string
  name: string
  type: string         // 'KnowledgeArea' | 'Position' | 'Skill' | ...
  position_count?: number
  skill_count?: number
  proficiency?: string
  category?: string
}

const props = defineProps<{
  node: TooltipNode | null
  x: number
  y: number
  visible: boolean
}>()

const typeInfo = computed(() =>
  TYPE_INFO[props.node?.type ?? ''] ?? { label: props.node?.type ?? '', color: '#64748b' }
)

const stats = computed(() => {
  if (!props.node) return []
  const items: { label: string; value: string | number }[] = []
  if (props.node.position_count != null) items.push({ label: '岗位', value: props.node.position_count })
  if (props.node.skill_count != null) items.push({ label: '技能', value: props.node.skill_count })
  if (props.node.proficiency) items.push({ label: '熟练度', value: props.node.proficiency })
  if (props.node.category) items.push({ label: '分类', value: props.node.category })
  return items
})
</script>

<template>
  <Teleport to="body">
    <Transition name="tooltip3d">
      <div
        v-if="visible && node"
        class="node-tooltip-3d"
        :style="{ left: `${x + 16}px`, top: `${y - 8}px` }"
      >
        <!-- Type badge -->
        <div class="tt-badge" :style="{ background: typeInfo.color + '22', color: typeInfo.color, borderColor: typeInfo.color + '44' }">
          {{ typeInfo.label }}
        </div>

        <!-- Node name -->
        <div class="tt-name">{{ node.name }}</div>

        <!-- Stats row -->
        <div v-if="stats.length" class="tt-stats">
          <div v-for="s in stats" :key="s.label" class="tt-stat">
            <span class="tt-stat-label">{{ s.label }}</span>
            <span class="tt-stat-value">{{ s.value }}</span>
          </div>
        </div>

        <!-- Glow accent line -->
        <div class="tt-glow-line" :style="{ background: `linear-gradient(90deg, ${typeInfo.color}, transparent)` }" />
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.node-tooltip-3d {
  position: fixed;
  z-index: 10000;
  pointer-events: none;
  min-width: 160px;
  max-width: 280px;
  padding: 10px 14px 12px;
  background: rgba(10, 14, 26, 0.92);
  backdrop-filter: blur(16px) saturate(1.5);
  -webkit-backdrop-filter: blur(16px) saturate(1.5);
  border: 1px solid rgba(100, 116, 139, 0.25);
  border-radius: 12px;
  box-shadow:
    0 0 20px rgba(34, 211, 238, 0.08),
    0 8px 24px rgba(0, 0, 0, 0.4);
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  transform: translateY(0);
}

.tt-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid;
  margin-bottom: 6px;
}

.tt-name {
  font-size: 13px;
  font-weight: 700;
  color: #e2e8f0;
  line-height: 1.3;
  margin-bottom: 6px;
}

.tt-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
}

.tt-stat {
  display: flex;
  flex-direction: column;
}

.tt-stat-label {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #64748b;
}

.tt-stat-value {
  font-size: 13px;
  font-weight: 700;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.tt-glow-line {
  position: absolute;
  bottom: 0;
  left: 14px;
  right: 14px;
  height: 1px;
  border-radius: 1px;
  opacity: 0.5;
}

/* Transition */
.tooltip3d-enter-active {
  transition: opacity 0.15s ease-out, transform 0.15s ease-out;
}
.tooltip3d-leave-active {
  transition: opacity 0.1s ease-in;
}
.tooltip3d-enter-from {
  opacity: 0;
  transform: translateY(4px);
}
.tooltip3d-leave-to {
  opacity: 0;
}
</style>
