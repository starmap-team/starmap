<script setup lang="ts">
/**
 * MatchFlow — business-flow diagram for MatchDiagnosis page .
 *
 *: makes the module-D pipeline visible so a new user
 * immediately sees how the 5-step match wizard fits into the broader
 * StarMap architecture.
 *
 * 用户上传简历(PDF/Word)
 * ↓
 * 文档解析 (pdfplumber / python-docx)
 * ↓
 * LLM 结构化抽取 (星火 / Qwen 双模型交叉验证)
 * ↓
 * 技能归一化 (别名映射 + 向量相似度)
 * ↓
 * 与目标岗位对比 (Neo4j REQUIRES 关系)
 * ↓
 * 差距分析 + 学习路径 ( 通胀指数参考)
 *
 * Each step is clickable: it jumps the wizard to the corresponding step
 * (upload / position / radar / gap / learn) so the user can navigate
 * the page by business concept rather than wizard tab.
 */
import type { Component } from 'vue'
import {
  Document,
  Reading,
  MagicStick,
  Connection,
  DataAnalysis,
  Reading as LearnIcon,
} from '@element-plus/icons-vue'

interface FlowNode {
  key: string
  label: string
  detail: string
  icon: Component
  step: number  // 0-4 in MatchDiagnosis wizard
  color: string
}

const nodes: FlowNode[] = [
  {
    key: 'parse',
    label: '文档解析',
    detail: '自动识别 PDF、DOCX 等格式 → 提取纯文本',
    icon: Document,
    step: 0,
    color: '#3b82f6',
  },
  {
    key: 'extract',
    label: '智能抽取',
    detail: '双模型交叉验证 (星火 + Qwen)',
    icon: MagicStick,
    step: 0,
    color: '#8b5cf6',
  },
  {
    key: 'normalize',
    label: '技能归一化',
    detail: '别名映射 + 向量相似度',
    icon: Reading,
    step: 0,
    color: '#06b6d4',
  },
  {
    key: 'compare',
    label: '岗位对比',
    detail: '查询岗位与技能的关联关系',
    icon: Connection,
    step: 2,
    color: '#10b981',
  },
  {
    key: 'gap',
    label: '差距分析',
    detail: '与目标岗位对比',
    icon: DataAnalysis,
    step: 3,
    color: '#f59e0b',
  },
  {
    key: 'learn',
    label: '学习路径',
    detail: '基于差距生成推荐',
    icon: LearnIcon,
    step: 4,
    color: '#ec4899',
  },
]

const emit = defineEmits<{
  (e: 'navigate', step: number): void
}>()

function clickNode(node: FlowNode) {
  emit('navigate', node.step)
}
</script>

<template>
  <div class="match-flow">
    <div
      v-for="(node, idx) in nodes"
      :key="node.key"
      class="flow-node"
      :style="{ background: node.color }"
      role="button"
      tabindex="0"
      @click="clickNode(node)"
      @keyup.enter="clickNode(node)"
    >
      <div class="node-icon">
        <el-icon :size="20">
          <component :is="node.icon" />
        </el-icon>
      </div>
      <div class="node-label">
        {{ node.label }}
      </div>
      <div class="node-detail">
        {{ node.detail }}
      </div>
      <div
        v-if="idx < nodes.length - 1"
        class="flow-arrow"
      >
        →
      </div>
    </div>
  </div>
</template>

<style scoped>
.match-flow {
  display: flex;
  flex-direction: row;
  gap: 0;
  align-items: stretch;
  flex-wrap: wrap;
}

.flow-node {
  position: relative;
  flex: 1 1 140px;
  min-width: 140px;
  padding: 12px 10px;
  border-radius: var(--radius-lg);
  color: white;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  margin-right: 14px;
  margin-bottom: 6px;
}

.flow-node:last-of-type {
  margin-right: 0;
}

.flow-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.flow-node:focus {
  outline: 2px solid var(--ring);
  outline-offset: 2px;
}

.node-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-md);
}

.node-label {
  font-size: var(--font-size-sm);
  font-weight: 700;
  letter-spacing: 0.01em;
}

.node-detail {
  font-size: var(--font-size-xs);
  opacity: 0.85;
  line-height: 1.4;
}

.flow-arrow {
  position: absolute;
  right: -12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 18px;
  font-weight: 700;
  color: var(--muted-foreground);
  z-index: 1;
  pointer-events: none;
}

@media (max-width: 768px) {
  .flow-node {
    flex: 1 1 calc(50% - 14px);
  }
  .flow-node:nth-of-type(2n) {
    margin-right: 0;
  }
}
</style>