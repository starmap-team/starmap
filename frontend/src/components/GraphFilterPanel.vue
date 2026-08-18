<script setup lang="ts">
/**
 * GraphFilterPanel — 左侧可折叠筛选面板
 *
 * Sprint C-3: 集中 domain/tech_stack/level radio、layout toggle、
 * 节点上限 slider、熟练度 chips、演化开关、图例。
 * 默认 240px 宽，可通过 4px 握手柄折叠到 0。
 */
import { ref, computed } from 'vue'
import { ArrowLeft, ArrowRight, Connection } from '@element-plus/icons-vue'
import type { OverviewMode, ViewLayer } from '@/stores/graph'
import { PROFICIENCY_LEVELS } from '@/constants/labels'

const props = withDefaults(defineProps<{
  overviewMode: OverviewMode
  layoutMode: 'force' | 'dagre' | 'radial'
  maxNodesLimit: number
  proficiencyFilter: string[]
  showEvolution: boolean
  currentLayer: ViewLayer
 /** KA color legend: { name, color, count } */
  legend?: { name: string; color: string; count: number }[]
  nodeCount?: number
}>(), {
  legend: () => [],
  nodeCount: 0,
})

const emit = defineEmits<{
  'update:overviewMode': [mode: OverviewMode]
  toggleLayout: []
  maxNodesChange: [value: number]
  proficiencyFilter: [value: string[]]
  toggleEvolution: []
}>()

const collapsed = ref(false)
const panelWidth = computed(() => collapsed.value ? 0 : 240)

const OVERVIEW_OPTIONS: { value: OverviewMode; label: string }[] = [
  { value: 'domain', label: '技术领域' },
  { value: 'tech_stack', label: '技术栈' },
  { value: 'level', label: '职级分组' },
]

const LAYOUT_OPTIONS: { value: 'force' | 'dagre' | 'radial'; label: string; icon: string }[] = [
  { value: 'force', label: '力', icon: '⟐' },
  { value: 'dagre', label: '层', icon: '≡' },
  { value: 'radial', label: '环', icon: '◎' },
]

function onProficiencyToggle(level: string) {
  const current = [...props.proficiencyFilter]
  const idx = current.indexOf(level)
  if (idx >= 0) {
    if (current.length > 1) current.splice(idx, 1)
  } else {
    current.push(level)
  }
  emit('proficiencyFilter', current)
}

const layoutIndex = computed(() => LAYOUT_OPTIONS.findIndex(o => o.value === props.layoutMode))

const layoutNextLabel = computed(() => {
  const next = LAYOUT_OPTIONS[(layoutIndex.value + 1) % LAYOUT_OPTIONS.length]
  return `${next.icon} ${next.label}`
})
</script>

<template>
  <div
    class="filter-panel"
    :class="{ collapsed }"
    :style="{ width: panelWidth + 'px' }"
  >
    <!-- Collapse handle -->
    <button
      class="filter-panel__handle"
      :aria-label="collapsed ? '展开筛选面板' : '收起筛选面板'"
      :title="collapsed ? '展开筛选面板' : '收起筛选面板'"
      @click="collapsed = !collapsed"
    >
      <el-icon :size="12">
        <ArrowLeft v-if="!collapsed" />
        <ArrowRight v-else />
      </el-icon>
    </button>

    <div
      v-show="!collapsed"
      class="filter-panel__inner"
    >
      <!-- Section: Overview Mode -->
      <div class="filter-section">
        <div class="filter-section__label">
          视图模式
        </div>
        <el-radio-group
          :model-value="overviewMode"
          size="small"
          @change="(v: string) => emit('update:overviewMode', v as OverviewMode)"
        >
          <el-radio-button
            v-for="opt in OVERVIEW_OPTIONS"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <!-- Section: Layout -->
      <div class="filter-section">
        <div class="filter-section__label">
          布局模式
        </div>
        <el-button
          size="small"
          class="layout-btn"
          @click="emit('toggleLayout')"
        >
          {{ layoutNextLabel }}
        </el-button>
      </div>

      <!-- Section: Max Nodes -->
      <div class="filter-section">
        <div class="filter-section__label">
          节点上限
          <span class="filter-section__value">{{ maxNodesLimit }}</span>
        </div>
        <el-slider
          :model-value="maxNodesLimit"
          :min="20"
          :max="500"
          :step="10"
          size="small"
          :show-tooltip="false"
          @update:model-value="(v: number | number[]) => emit('maxNodesChange', Array.isArray(v) ? v[0] : v)"
        />
      </div>

      <!-- Section: Proficiency -->
      <div class="filter-section">
        <div class="filter-section__label">
          熟练度筛选
        </div>
        <div class="proficiency-chips">
          <el-check-tag
            v-for="level in PROFICIENCY_LEVELS"
            :key="level"
            :checked="proficiencyFilter.includes(level)"
            size="small"
            @change="onProficiencyToggle(level)"
          >
            {{ level }}
          </el-check-tag>
        </div>
      </div>

      <!-- Section: Evolution -->
      <div class="filter-section">
        <el-button
          size="small"
          :type="showEvolution ? 'warning' : 'default'"
          :style="{ width: '100%' }"
          @click="emit('toggleEvolution')"
        >
          <el-icon
            :size="14"
            style="margin-right: 4px"
          >
            <Connection />
          </el-icon>
          演化视图 {{ showEvolution ? 'ON' : 'OFF' }}
        </el-button>
      </div>

      <!-- Section: Legend -->
      <div
        v-if="legend.length"
        class="filter-section"
      >
        <div class="filter-section__label">
          图例
          <span class="filter-section__value">{{ nodeCount }} 节点</span>
        </div>
        <div class="legend-list">
          <div
            v-for="item in legend"
            :key="item.name"
            class="legend-item"
          >
            <span
              class="legend-dot"
              :style="{ background: item.color }"
            />
            <span class="legend-name">{{ item.name }}</span>
            <span class="legend-count">{{ item.count }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filter-panel {
  position: relative;
  flex-shrink: 0;
  background: var(--card);
  border-right: 1px solid var(--border);
  transition: width var(--duration-slow) var(--ease-out);
  overflow: hidden;
  z-index: var(--z-sticky);
}
.filter-panel.collapsed {
  border-right-color: transparent;
}
.filter-panel__handle {
  position: absolute;
  right: -12px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 2;
  width: 24px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  color: var(--muted-foreground);
  cursor: pointer;
  transition: color var(--duration-fast), background var(--duration-fast);
  padding: 0;
}
.filter-panel__handle:hover {
  color: var(--primary);
  background: var(--primary-ghost);
}
.filter-panel__inner {
  padding: var(--space-3) var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
  overflow-y: auto;
}
.filter-panel__inner::-webkit-scrollbar { width: 3px; }
.filter-section { display: flex; flex-direction: column; gap: var(--space-2); }
.filter-section__label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted-foreground);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-section__value {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

/* Layout button */
.layout-btn { width: 100%; font-family: var(--font-mono); font-size: 12px; }

/* Proficiency chips */
.proficiency-chips { display: flex; gap: var(--space-1-5); flex-wrap: wrap; }

/* Legend */
.legend-list { display: flex; flex-direction: column; gap: var(--space-1); }
.legend-item { display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-xs); }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.legend-name { flex: 1; color: var(--foreground); }
.legend-count { color: var(--muted-foreground); font-variant-numeric: tabular-nums; }

/* Responsive: auto-collapse on mobile */
@media (max-width: 768px) {
  .filter-panel { width: 0 !important; }
  .filter-panel__handle { right: -20px; }
}
</style>
