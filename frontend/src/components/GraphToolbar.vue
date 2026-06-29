<script setup lang="ts">
/**
 * GraphToolbar — floating zoom/layout controls for the graph canvas
 * Emits zoom/layout events; parent handles the actual graph operations.
 */
import { ZoomIn, ZoomOut, Aim } from '@element-plus/icons-vue'

defineProps<{
  nodeCount: number
  layoutMode: 'force' | 'dagre'
}>()

defineEmits<{
  zoomIn: []
  zoomOut: []
  zoomFit: []
  toggleLayout: []
}>()
</script>

<template>
  <div class="graph-toolbar glass">
    <el-tooltip content="放大" placement="top">
      <button class="tb-btn" @click="$emit('zoomIn')"><el-icon><ZoomIn /></el-icon></button>
    </el-tooltip>
    <el-tooltip content="缩小" placement="top">
      <button class="tb-btn" @click="$emit('zoomOut')"><el-icon><ZoomOut /></el-icon></button>
    </el-tooltip>
    <el-tooltip content="居中" placement="top">
      <button class="tb-btn" @click="$emit('zoomFit')"><el-icon><Aim /></el-icon></button>
    </el-tooltip>
    <span class="tb-divider"></span>
    <el-tooltip :content="layoutMode === 'force' ? '切换分层' : '切换力导向'" placement="top">
      <button class="tb-btn" @click="$emit('toggleLayout')">
        <span class="tb-label">{{ layoutMode === 'force' ? '力' : '层' }}</span>
      </button>
    </el-tooltip>
    <span class="tb-divider"></span>
    <span class="tb-count">{{ nodeCount }} 节点</span>
  </div>
</template>

<style scoped>
.graph-toolbar {
  position: absolute;
  top: var(--space-3);
  left: var(--space-3);
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--card) 90%, transparent);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: var(--shadow-sm);
}
.tb-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  border-radius: var(--radius-md);
  color: var(--muted-foreground);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.tb-btn:hover {
  color: var(--foreground);
  background: var(--accent);
}
.tb-btn:active {
  transform: scale(0.92);
}
.tb-divider {
  width: 1px;
  height: 16px;
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
  font-size: var(--font-size-xs);
  font-weight: 600;
}
</style>