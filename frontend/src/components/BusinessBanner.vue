<script setup lang="ts">
/**
 * BusinessBanner — 可复用的业务说明横幅组件
 *
 * 提取自 EvolutionDashboard.vue / PipelineMonitor.vue / DataSources.vue 等页面中
 * 重复出现的 `el-alert` 业务说明横幅，统一封装为组件。
 *
 * Usage:
 *   <BusinessBanner
 *     type="warning"
 *     title="§5.2 演化分析 + §7.5 能力通胀指数 (CII)"
 *     description="本看板展示岗位技能图谱的演化趋势..."
 *     meta="后端: /evolution/* · 数据源: evolution_changelog"
 *   />
 */

type AlertType = 'success' | 'warning' | 'info' | 'error'

withDefaults(defineProps<{
  /** Element Plus alert type */
  type?: AlertType
  /** Banner title (supports HTML) */
  title: string
  /** Main description text (supports HTML) */
  description: string
  /** Optional metadata line with `<code>` tags */
  meta?: string
}>(), {
  type: 'info',
  meta: '',
})
</script>

<template>
  <el-alert
    :type="type"
    :closable="false"
    :show-icon="true"
    class="business-banner"
  >
    <template #title>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <span v-html="title" />
    </template>
    <!-- eslint-disable-next-line vue/no-v-html -->
    <p v-html="description" />
    <!-- eslint-disable vue/no-v-html -->
    <p
      v-if="meta"
      class="banner-meta"
      v-html="meta"
    />
    <!-- eslint-enable vue/no-v-html -->
  </el-alert>
</template>

<style scoped>
.business-banner {
  margin-bottom: var(--space-4);
  border-radius: var(--radius-lg);
}
.business-banner :deep(p) {
  margin: 0 0 var(--space-1) 0;
  line-height: 1.6;
  font-size: var(--font-size-sm);
}
.business-banner :deep(p:last-child) {
  margin-bottom: 0;
}
.banner-meta {
  margin-top: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  opacity: 0.8;
}
.banner-meta :deep(code) {
  background: var(--muted);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 11px;
}
</style>
