<script setup lang="ts">
/**
 * GraphToolbar - floating zoom/layout/filter controls for the graph canvas
 * Enhanced with filtering, node limiting, layout options, and 3D camera controls.
 */
import { ref } from 'vue'
import { ZoomIn, ZoomOut, Aim, Filter, RefreshRight, VideoCamera, Position, Compass } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  nodeCount: number
  layoutMode: 'force' | 'dagre' | 'radial'
  is3D?: boolean
  autoRotate?: boolean
  maxNodes?: number
  selectedProficiencies?: string[]
}>(), {
  is3D: false,
  autoRotate: false,
  maxNodes: 80,
  selectedProficiencies: () => ['精通', '熟悉', '了解'],
})

const emit = defineEmits<{
  zoomIn: []
  zoomOut: []
  zoomFit: []
  toggleLayout: []
  resetHighlight: []
  maxNodesChange: [value: number]
  proficiencyFilter: [levels: string[]]
  cameraPreset: [preset: 'overview' | 'domain' | 'position']
  resetCamera: []
  toggleAutoRotate: []
}>()

const showFilters = ref(false)

function toggleProficiency(level: string) {
  const current = [...props.selectedProficiencies]
  const idx = current.indexOf(level)
  if (idx >= 0) {
    current.splice(idx, 1)
  } else {
    current.push(level)
  }
  emit('proficiencyFilter', current)
}
</script>

<template>
  <div class="graph-toolbar glass">
    <!-- Zoom controls -->
    <el-tooltip
      content="放大"
      placement="top"
    >
      <button
        class="tb-btn"
        @click="emit('zoomIn')"
      >
        <el-icon><ZoomIn /></el-icon>
      </button>
    </el-tooltip>
    <el-tooltip
      content="缩小"
      placement="top"
    >
      <button
        class="tb-btn"
        @click="emit('zoomOut')"
      >
        <el-icon><ZoomOut /></el-icon>
      </button>
    </el-tooltip>
    <el-tooltip
      content="居中适配"
      placement="top"
    >
      <button
        class="tb-btn"
        @click="emit('zoomFit')"
      >
        <el-icon><Aim /></el-icon>
      </button>
    </el-tooltip>
    <span class="tb-divider" />

    <!-- Layout toggle -->
    <el-tooltip
      :content="layoutMode === 'force' ? '切换分层布局' : layoutMode === 'dagre' ? '切换环形布局' : '切换力导向'"
      placement="top"
    >
      <button
        class="tb-btn"
        @click="emit('toggleLayout')"
      >
        <span class="tb-label">{{ layoutMode === 'force' ? '力' : layoutMode === 'dagre' ? '层' : '环' }}</span>
      </button>
    </el-tooltip>

    <!-- Reset highlight -->
    <el-tooltip
      content="重置高亮"
      placement="top"
    >
      <button
        class="tb-btn"
        @click="emit('resetHighlight')"
      >
        <el-icon><RefreshRight /></el-icon>
      </button>
    </el-tooltip>

    <!-- Filter toggle -->
    <el-tooltip
      content="筛选器"
      placement="top"
    >
      <button
        class="tb-btn"
        :class="{ 'tb-btn--active': showFilters }"
        @click="showFilters = !showFilters"
      >
        <el-icon><Filter /></el-icon>
      </button>
    </el-tooltip>

    <!-- 3D Camera controls (only shown in 3D mode) -->
    <template v-if="is3D">
      <span class="tb-divider" />
      <el-tooltip
        content="全景俯瞰"
        placement="top"
      >
        <button
          class="tb-btn tb-btn--3d"
          @click="emit('cameraPreset', 'overview')"
        >
          <el-icon><VideoCamera /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip
        content="领域聚焦"
        placement="top"
      >
        <button
          class="tb-btn tb-btn--3d"
          @click="emit('cameraPreset', 'domain')"
        >
          <el-icon><Aim /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip
        content="岗位网络"
        placement="top"
      >
        <button
          class="tb-btn tb-btn--3d"
          @click="emit('cameraPreset', 'position')"
        >
          <el-icon><Position /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip
        content="重置视角"
        placement="top"
      >
        <button
          class="tb-btn"
          @click="emit('resetCamera')"
        >
          <el-icon><Compass /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip
        :content="autoRotate ? '停止旋转' : '自动旋转'"
        placement="top"
      >
        <button
          class="tb-btn"
          :class="{ 'tb-btn--active': autoRotate }"
          @click="emit('toggleAutoRotate')"
        >
          <span class="tb-label">{{ autoRotate ? '⏸' : '🔄' }}</span>
        </button>
      </el-tooltip>
    </template>

    <span class="tb-divider" />
    <span class="tb-count">{{ nodeCount }} 节点</span>

    <!-- Expandable filter panel -->
    <div
      v-if="showFilters"
      class="filter-panel glass"
    >
      <div class="filter-section">
        <span class="filter-label">节点上限</span>
        <el-slider
          :model-value="props.maxNodes"
          :min="20"
          :max="500"
          :step="10"
          size="small"
          @change="(v: number) => emit('maxNodesChange', v)"
        />
      </div>
      <div class="filter-section">
        <span class="filter-label">熟练度</span>
        <div class="prof-chips">
          <button
            v-for="level in ['精通', '熟悉', '了解']"
            :key="level"
            class="prof-chip"
            :class="{ 'prof-chip--active': props.selectedProficiencies.includes(level) }"
            @click="toggleProficiency(level)"
          >
            {{ level }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.graph-toolbar {
  position: absolute;
  top: var(--space-3);
  left: var(--space-3);
  display: flex;
  align-items: center;
  gap: var(--space-0-5);
  padding: var(--space-1);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--card) 88%, transparent);
  backdrop-filter: blur(16px) saturate(1.8);
  -webkit-backdrop-filter: blur(16px) saturate(1.8);
  box-shadow: var(--shadow-sm);
  z-index: 10;
}
.tb-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  background: none;
  border-radius: var(--radius-md);
  color: var(--muted-foreground);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.tb-btn:hover {
  color: var(--foreground);
  background: var(--sidebar-hover);
}
.tb-btn:active { transform: scale(0.92); }
.tb-btn--active {
  color: var(--primary);
  background: var(--primary-ghost);
}
.tb-btn--3d {
  color: #22d3ee;
}
.tb-btn--3d:hover {
  color: #67e8f9;
  background: rgba(34, 211, 238, 0.1);
}
.tb-divider {
  width: 1px;
  height: 14px;
  background: var(--border);
  margin: 0 2px;
}
.tb-count {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  padding: 0 var(--space-2);
  font-variant-numeric: tabular-nums;
}
.tb-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.filter-panel {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: var(--space-1);
  padding: var(--space-3);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--card) 95%, transparent);
  backdrop-filter: blur(20px) saturate(1.8);
  box-shadow: var(--shadow-lg);
  min-width: 200px;
  z-index: 20;
}
.filter-section {
  margin-bottom: var(--space-3);
}
.filter-section:last-child { margin-bottom: 0; }
.filter-label {
  display: block;
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--muted-foreground);
  margin-bottom: var(--space-1);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.prof-chips {
  display: flex;
  gap: var(--space-1);
}
.prof-chip {
  padding: 3px 10px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted-foreground);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all var(--duration-fast);
}
.prof-chip:hover {
  border-color: var(--primary);
  color: var(--primary);
}
.prof-chip--active {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--primary-foreground);
}
</style>