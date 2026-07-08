<script setup lang="ts">
import type { ViewLayer } from "@/stores/graph"

defineProps<{
  breadcrumb: { label: string; layer: ViewLayer; action?: () => void }[]
  viewMode: '2d' | '3d'
  showEvolution: boolean
  showOverviewRadio: boolean
  overviewMode: 'domain' | 'tech_stack' | 'level'
  currentLayer: ViewLayer
}>()

const emit = defineEmits<{
  setViewMode: [mode: '2d' | '3d']
  toggleEvolution: []
  overviewModeChange: [mode: string]
}>()
</script>

<template>
  <div class="graph-controls">
    <div class="controls-left">
      <nav class="graph-breadcrumb">
        <template
          v-for="(item, i) in breadcrumb"
          :key="i"
        >
          <span
            class="gb-item"
            :class="{ active: i === breadcrumb.length - 1 }"
            @click="i < breadcrumb.length - 1 && item.action?.()"
          >{{ item.label }}</span>
          <span
            v-if="i < breadcrumb.length - 1"
            class="gb-sep"
          >></span>
        </template>
      </nav>
      <el-radio-group
        v-if="showOverviewRadio"
        :model-value="overviewMode"
        size="small"
        class="view-tabs"
        @change="(mode: string) => emit('overviewModeChange', mode)"
      >
        <el-radio-button value="domain">
          领域
        </el-radio-button>
        <el-radio-button value="tech_stack">
          技术栈
        </el-radio-button>
        <el-radio-button value="level">
          级别
        </el-radio-button>
      </el-radio-group>
    </div>
    <div class="controls-right">
      <div class="view-mode-toggle">
        <button
          class="vm-btn"
          :class="{ 'vm-btn--active': viewMode === '2d' }"
          @click="emit('setViewMode', '2d')"
        >
          2D
        </button>
        <button
          class="vm-btn"
          :class="{ 'vm-btn--active': viewMode === '3d' }"
          @click="emit('setViewMode', '3d')"
        >
          3D
        </button>
        <span
          class="vm-indicator"
          :class="{ 'vm-indicator--3d': viewMode === '3d' }"
        />
      </div>
      <div class="graph-legend">
        <span class="legend-item"><span class="ld-dot ld-dot--domain" />领域</span>
        <span class="legend-item"><span class="ld-dot ld-dot--position" />岗位</span>
        <span class="legend-item"><span class="ld-dot ld-dot--skill" />技能</span>
        <span
          v-if="showEvolution"
          class="legend-item"
        ><span class="ld-line" />演化</span>
      </div>
      <el-button
        size="small"
        :type="showEvolution ? 'primary' : 'default'"
        text
        @click="emit('toggleEvolution')"
      >
        {{ showEvolution ? '隐藏演化' : '显示演化' }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.graph-controls { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-3); padding: var(--space-2) var(--space-4); background: var(--card); border: 1px solid var(--border); border-radius: var(--radius-xl); box-shadow: var(--shadow-xs); }
.controls-left { display: flex; align-items: center; gap: var(--space-4); }
.controls-right { display: flex; align-items: center; gap: var(--space-3); }
.graph-breadcrumb { display: flex; align-items: center; gap: var(--space-1-5); font-size: var(--font-size-sm); }
.gb-item { color: var(--muted-foreground); cursor: pointer; padding: 3px 8px; border-radius: var(--radius-sm); transition: all var(--duration-fast); font-weight: 500; }
.gb-item:hover:not(.active) { color: var(--primary); background: var(--primary-ghost); }
.gb-item.active { color: var(--foreground); font-weight: 600; cursor: default; }
.gb-sep { color: var(--border); font-size: var(--font-size-xs); margin: 0 2px; }
.view-tabs { --el-radio-button-checked-bg-color: var(--primary); --el-radio-button-checked-border-color: var(--primary); }
.view-tabs .el-radio-button__inner { font-size: var(--font-size-xs); font-weight: 500; letter-spacing: 0.02em; padding: 6px 14px; transition: all var(--duration-normal) var(--ease-out); }
.view-mode-toggle { display: flex; align-items: center; position: relative; background: color-mix(in srgb, var(--muted-foreground) 8%, transparent); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 2px; }
.vm-btn { position: relative; z-index: 2; padding: 4px 14px; border: none; background: none; color: var(--muted-foreground); font-size: var(--font-size-xs); font-weight: 700; letter-spacing: 0.04em; cursor: pointer; border-radius: var(--radius-md); transition: color var(--duration-fast) var(--ease-out); }
.vm-btn--active { color: var(--primary-foreground); }
.vm-indicator { position: absolute; top: 2px; left: 2px; width: calc(50% - 2px); height: calc(100% - 4px); background: var(--primary); border-radius: var(--radius-md); transition: transform var(--duration-normal) var(--ease-out); z-index: 1; box-shadow: 0 1px 4px color-mix(in srgb, var(--primary) 40%, transparent); }
.vm-indicator--3d { transform: translateX(100%); }
.graph-legend { display: flex; align-items: center; gap: var(--space-3); font-size: var(--font-size-xs); color: var(--muted-foreground); }
.legend-item { display: flex; align-items: center; gap: var(--space-1); }
.ld-dot { width: 8px; height: 8px; border-radius: 50%; }
.ld-line { width: 16px; height: 0; border-top: 2px dashed var(--destructive); }
.ld-dot--domain { background: var(--chart-3); }
.ld-dot--position { background: var(--chart-1); }
.ld-dot--skill { background: var(--success); }

@media (max-width: 768px) {
  .controls-left, .controls-right { flex-wrap: wrap; }
}
</style>
