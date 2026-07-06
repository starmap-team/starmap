<script setup lang="ts">
/**
 * 数据源管理面板
 * 展示数据源卡片列表或空状态
 */
import DataSourceCard from '@/components/DataSourceCard.vue'
import type { DataSource } from '@/stores/pipeline'

defineProps<{
  dataSources: DataSource[]
  loading: boolean
}>()
</script>

<template>
  <el-card
    v-loading="loading"
    shadow="never"
    class="sources-panel"
  >
    <template #header>
      <div class="panel-header">
        <span>数据源管理</span>
        <el-tag
          size="small"
          effect="plain"
          round
        >
          {{ dataSources.length }} 个数据源
        </el-tag>
      </div>
    </template>
    <el-row
      v-if="dataSources.length"
      :gutter="12"
    >
      <el-col
        v-for="source in dataSources"
        :key="source.id"
        :xl="12"
        :lg="12"
        :md="12"
        :sm="24"
        class="mb-4"
      >
        <DataSourceCard :source="source" />
      </el-col>
    </el-row>
    <div
      v-else
      class="custom-empty"
    >
      <div class="empty-icon-wrapper">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <ellipse
            cx="12"
            cy="5"
            rx="9"
            ry="3"
          />
          <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
          <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
        </svg>
      </div>
      <p class="empty-text">
        数据源待加载
      </p>
      <p class="empty-hint-text">
        数据源信息将在首次同步后展示
      </p>
    </div>
  </el-card>
</template>

<style scoped>
/* 面板头部 */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 空状态 */
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-8) var(--space-4);
  text-align: center;
}
.empty-icon-wrapper {
  color: var(--muted-foreground);
  opacity: 0.4;
  margin-bottom: var(--space-3);
}
.empty-text {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
}
.empty-hint-text {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}

.mb-4 { margin-bottom: var(--space-4); }
</style>
