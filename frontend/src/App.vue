<script setup lang="ts">
// 星图 StarMap 根组件
</script>

<template>
  <router-view v-slot="{ Component }">
    <transition
      name="page-fade"
      mode="out-in"
    >
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<style>
/* ═══════════════════════════════════════
   星图 StarMap — 全局样式
   ═══════════════════════════════════════ */

:root {
  --starmap-primary: #409eff;
  --starmap-success: #67c23a;
  --starmap-warning: #e6a23c;
  --starmap-danger: #f56c6c;
  --starmap-dark: #001529;
  --starmap-bg: #f5f7fa;
  --starmap-border: #ebeef5;
  --starmap-text: #303133;
  --starmap-text-secondary: #606266;
  --starmap-text-muted: #909399;
  --starmap-radius: 8px;
  --starmap-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
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

/* 页面过渡动画 */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease;
}
.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
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
