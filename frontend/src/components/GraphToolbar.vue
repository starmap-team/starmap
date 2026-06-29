<script setup lang="ts">
/**
 * GraphToolbar - floating zoom/layout controls for the graph canvas
 * Obsidian-style: clean, minimal, functional
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
    <el-tooltip
      content="放大"
      placement="top"
    >
      <button
        class="tb-btn"
        @click="$emit('zoomIn')"
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
        @click="$emit('zoomOut')"
      >
        <el-icon><ZoomOut /></el-icon>
      </button>
    </el-tooltip>
    <el-tooltip
      content="居中"
      placement="top"
    >
      <button
        class="tb-btn"
        @click="$emit('zoomFit')"
      >
        <el-icon><Aim /></el-icon>
      </button>
    </el-tooltip>
    <span class="tb-divider" />
    <el-tooltip
      :content="layoutMode === 'force' ? '切换分层' : '切换力导向'"
      placement="top"
    >
      <button
        class="tb-btn"
        @click="$emit('toggleLayout')"
      >
        <span class="tb-label">{{ layoutMode === 'force' ? '力' : '层' }}</span>
      </button>
    </el-tooltip>
    <span class="tb-divider" />
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
  gap: var(--space-0-5);
  padding: var(--space-1);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--card) 88%, transparent);
  backdrop-filter: blur(16px) saturate(1.8);
  -webkit-backdrop-filter: blur(16px) saturate(1.8);
  box-shadow: var(--shadow-sm);
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
</style>
