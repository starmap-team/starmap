<script setup lang="ts">
/**
 * PipelineMonitor KPI 卡片组 — 拆分
 *
 * 纯展示：4 列响应式 KPI 卡片。无事件，无副作用。
 * 从 PipelineMonitor.vue:543-594 抽出。
 */
import type { Component } from 'vue'

interface KpiCard {
  label: string
  color: string
 // element-plus icon name (resolved via global registration) or Component
  icon: Component | string
  value: string | number
  trend?: string
  sub: string
}

defineProps<{
  cards: KpiCard[]
}>()
</script>

<template>
  <el-row
    :gutter="16"
    class="mb-4"
  >
    <el-col
      v-for="card in cards"
      :key="card.label"
      :lg="6"
      :md="12"
      :sm="24"
      class="mb-4"
    >
      <el-card
        shadow="hover"
        class="kpi-card"
      >
        <div class="kpi-inner">
          <div
            class="kpi-icon"
            :style="{ background: card.color + '18', color: card.color }"
          >
            <el-icon size="22">
              <component :is="card.icon" />
            </el-icon>
          </div>
          <div class="kpi-body">
            <div class="kpi-label">
              {{ card.label }}
            </div>
            <div
              class="kpi-value"
              :style="{ color: card.color }"
            >
              {{ card.value }}
            </div>
            <div class="kpi-sub">
              <span
                v-if="card.trend && card.trend === 'up'"
                class="trend-up"
              >▲</span>
              <span
                v-else-if="card.trend && card.trend === 'down'"
                class="trend-down"
              >▼</span>
              {{ card.sub }}
            </div>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>
