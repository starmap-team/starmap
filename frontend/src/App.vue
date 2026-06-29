<script setup lang="ts">
// 星图 StarMap 根组件
</script>

<template>
  <router-view v-slot="{ Component, route }">
    <transition
      :name="(route.meta?.transition as string) || 'page-fade'"
      mode="out-in"
    >
      <component :is="Component" :key="route.path" />
    </transition>
  </router-view>
</template>

<style>
/* ════════════════════════════════════════
   星图 StarMap — 全局样式
   ════════════════════════════════════════ */

:root {
  --starmap-primary: #409eff;
  --starmap-success: #67c23a;
  --starmap-warning: #e6a23c;
  --starmap-danger: #f56c6c;
  --starmap-dark: #001529;
  --starmap-bg: #f5f7fa;
  --starmap-card-bg: #ffffff;
  --starmap-border: #ebeef5;
  --starmap-text: #303133;
  --starmap-text-secondary: #606266;
  --starmap-text-muted: #909399;
  --starmap-radius: 8px;
  --starmap-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

/* 暗色模式变量 */
html.dark {
  --starmap-bg: #0d1117;
  --starmap-card-bg: #161b22;
  --starmap-border: #30363d;
  --starmap-text: #e6edf3;
  --starmap-text-secondary: #b1bac4;
  --starmap-text-muted: #8b949e;
  --starmap-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
}

html.dark body {
  background: var(--starmap-bg);
  color: var(--starmap-text);
}

html.dark .el-card {
  background: var(--starmap-card-bg) !important;
  border-color: var(--starmap-border) !important;
  color: var(--starmap-text) !important;
}

html.dark .el-card__header {
  background: var(--starmap-card-bg) !important;
  border-bottom-color: var(--starmap-border) !important;
  color: var(--starmap-text) !important;
}

html.dark .el-table {
  --el-table-bg-color: var(--starmap-card-bg);
  --el-table-tr-bg-color: var(--starmap-card-bg);
  --el-table-header-bg-color: #1c2128;
  --el-table-text-color: var(--starmap-text);
  --el-table-header-text-color: var(--starmap-text-secondary);
  --el-table-border-color: var(--starmap-border);
  --el-table-row-hover-bg-color: #1c2128;
}

html.dark .el-table th.el-table__cell {
  background: #1c2128 !important;
  color: var(--starmap-text-secondary) !important;
}

html.dark .el-descriptions {
  --el-descriptions-item-bordered-label-background: #1c2128;
}

html.dark .el-drawer {
  background: var(--starmap-card-bg) !important;
}

html.dark .el-input__wrapper,
html.dark .el-textarea__inner {
  background: #1c2128 !important;
  border-color: var(--starmap-border) !important;
  color: var(--starmap-text) !important;
}

html.dark .el-step__title {
  color: var(--starmap-text-secondary) !important;
}

html.dark .el-step__title.is-process {
  color: var(--starmap-text) !important;
}

html.dark .el-breadcrumb__inner {
  color: var(--starmap-text-muted) !important;
}

html.dark .layout-footer {
  background: var(--starmap-card-bg) !important;
  border-top-color: var(--starmap-border) !important;
}

*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial,
    sans-serif;
  color: var(--starmap-text);
  background: var(--starmap-bg);
  line-height: 1.6;
}

/* 页面过渡动画 - fade */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.25s ease;
}
.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}

/* 页面过渡动画 - slide */
.page-slide-enter-active,
.page-slide-leave-active {
  transition: all 0.3s ease;
}
.page-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.page-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* 链接 */
a {
  color: var(--starmap-primary);
  text-decoration: none;
}
a:hover {
  color: #66b1ff;
}

/* 滚动条美化 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #c0c4cc;
}

/* Element Plus 卡片微调 */
.el-card {
  border-radius: var(--starmap-radius) !important;
  border: 1px solid var(--starmap-border) !important;
  background: var(--starmap-card-bg) !important;
}

.el-card__header {
  padding: 14px 20px !important;
  border-bottom: 1px solid var(--starmap-border) !important;
  font-weight: 600;
}

.el-card__body {
  padding: 20px !important;
}

/* Element Plus 按钮 */
.el-button--primary {
  --el-button-bg-color: var(--starmap-primary);
  --el-button-border-color: var(--starmap-primary);
}

/* Element Plus 步骤条 */
.el-steps {
  flex-wrap: wrap;
}

/* 表格微调 */
.el-table th.el-table__cell {
  background: #fafafa;
  color: var(--starmap-text-secondary);
  font-weight: 600;
}

/* 骨架屏动画 */
@keyframes skeleton-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.skeleton-block {
  background: #ebeef5;
  border-radius: 4px;
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}

html.dark .skeleton-block {
  background: #30363d;
}

/* 成功庆祝微动画 */
@keyframes celebrate-bounce {
  0% { transform: scale(1); }
  50% { transform: scale(1.08); }
  100% { transform: scale(1); }
}

.celebrate-anim {
  animation: celebrate-bounce 0.5s ease;
}

/* 全局 loading 条 */
.global-loading-bar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  z-index: 9999;
  background: linear-gradient(90deg, var(--starmap-primary), #67c23a);
  animation: loading-slide 1.5s ease-in-out infinite;
}

@keyframes loading-slide {
  0% { transform: translateX(-100%); }
  50% { transform: translateX(0); }
  100% { transform: translateX(100%); }
}

/* 响应式 */
@media (max-width: 768px) {
  html {
    font-size: 14px;
  }

  .el-card__body {
    padding: 14px !important;
  }

  .el-card__header {
    padding: 12px 14px !important;
  }
}
</style>
