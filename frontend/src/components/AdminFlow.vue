<script setup lang="ts">
/**
 * AdminFlow — visual business-flow diagram for the AdminOverview tab.
 *
 * Renders the StarMap 6-stage business loop as a connected pipeline:
 * 数据采集 → 智能抽取 → 图谱更新 → 人工审核 → 匹配诊断 → 学习路径
 *
 * Each stage is clickable and jumps to the corresponding page (or admin
 * tab via a window event). The aim is that a brand-new admin can land
 * on /admin and immediately see *where* in the business they are.
 */
import { useRouter } from 'vue-router'
import type { Component } from 'vue'
import {
  Coin,
  Document,
  Connection,
  CircleCheck,
  Monitor,
  Reading,
} from '@element-plus/icons-vue'

const router = useRouter()

interface FlowStage {
  key: string
  label: string
  description: string
  icon: Component
  color: string
  route: string  // for direct navigation
  adminTab?: string  // for admin-tab navigation via event
}

const stages: FlowStage[] = [
  {
    key: 'collect',
    label: '数据采集',
    description: '爬虫 + 第三方数据源',
    icon: Coin,
    color: '#3b82f6',
    route: '/datasources',
  },
  {
    key: 'extract',
    label: '智能抽取',
    description: 'LLM 提取技能 / 岗位',
    icon: Document,
    color: '#8b5cf6',
    route: '/extract',
  },
  {
    key: 'graph',
    label: '图谱更新',
    description: '更新知识图谱中的节点与关联',
    icon: Connection,
    color: '#06b6d4',
    route: '/',
  },
  {
    key: 'review',
    label: '人工审核',
    description: '低信任变更确认',
    icon: CircleCheck,
    color: '#f59e0b',
    route: '/admin',
    adminTab: 'content-review',
  },
  {
    key: 'match',
    label: '匹配诊断',
    description: '技能差距分析',
    icon: Monitor,
    color: '#10b981',
    route: '/match',
  },
  {
    key: 'learn',
    label: '学习路径',
    description: '推荐 + 进度跟踪',
    icon: Reading,
    color: '#ec4899',
    route: '/learning',
  },
]

function onClickStage(stage: FlowStage) {
  if (stage.adminTab) {
    window.dispatchEvent(new CustomEvent('admin:navigate', { detail: stage.adminTab }))
  } else {
    router.push(stage.route)
  }
}
</script>

<template>
  <div class="admin-flow">
    <div
      v-for="(stage, idx) in stages"
      :key="stage.key"
      class="flow-stage"
      :style="{ background: stage.color }"
      role="button"
      tabindex="0"
      @click="onClickStage(stage)"
      @keyup.enter="onClickStage(stage)"
    >
      <div class="stage-icon">
        <el-icon :size="22">
          <component :is="stage.icon" />
        </el-icon>
      </div>
      <div class="stage-label">
        {{ stage.label }}
      </div>
      <div class="stage-desc">
        {{ stage.description }}
      </div>
      <div
        v-if="idx < stages.length - 1"
        class="flow-arrow"
      >
        →
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-flow {
  display: flex;
  flex-direction: row;
  gap: 0;
  align-items: stretch;
  justify-content: space-between;
  flex-wrap: wrap;
}

.flow-stage {
  position: relative;
  flex: 1 1 130px;
  min-width: 130px;
  padding: 14px 12px;
  border-radius: var(--radius-lg);
  color: white;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  margin-right: 16px;
  margin-bottom: 8px;
}

.flow-stage:last-of-type {
  margin-right: 0;
}

.flow-stage:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
}

.flow-stage:focus {
  outline: 2px solid var(--ring);
  outline-offset: 2px;
}

.stage-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-md);
}

.stage-label {
  font-size: var(--font-size-sm);
  font-weight: 700;
  letter-spacing: 0.01em;
}

.stage-desc {
  font-size: var(--font-size-xs);
  opacity: 0.85;
  line-height: 1.4;
}

.flow-arrow {
  position: absolute;
  right: -14px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 22px;
  font-weight: 700;
  color: var(--muted-foreground);
  z-index: 1;
  pointer-events: none;
}

@media (max-width: 768px) {
  .flow-stage {
    flex: 1 1 calc(50% - 16px);
  }
  .flow-stage:nth-of-type(2n) {
    margin-right: 0;
  }
  .flow-stage:nth-of-type(2n)::after {
    content: '↓';
    position: absolute;
    right: 50%;
    bottom: -16px;
    transform: translateX(50%);
    font-size: 18px;
    color: var(--muted-foreground);
  }
}
</style>
