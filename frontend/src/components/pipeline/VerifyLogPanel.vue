<!--
  PipelineMonitor 闭环验证日志面板（Phase 03 Plan 03 从内联模板抽出）。
  按钮 → API → 状态变化 → 验证 的完整闭环展示。
-->
<script setup lang="ts">
import { Check, Close, Connection, Loading, Lock } from '@element-plus/icons-vue'
import type { ActionLog } from '@/composables/useVerifyLog'

defineProps<{
  logs: ActionLog[]
  isVerifying: boolean
}>()

const emit = defineEmits<{
  (e: 'clear'): void
}>()

function logTime(ts: number) {
  if (typeof ts !== 'number' || !Number.isFinite(ts) || ts < 0) return '--:--:--'
  return new Date(ts).toLocaleTimeString('zh-CN', { hour12: false })
}
</script>

<template>
  <el-card
    shadow="never"
    class="verify-log-card mb-4"
  >
    <template #header>
      <div class="panel-header">
        <span>
          <el-icon style="vertical-align: middle"><Check /></el-icon>
          闭环验证 (按钮 → API → 状态变化 → 验证)
          <!-- Phase 3.8.2: 持久化指示器 -->
          <el-tag
            v-if="logs.length > 0"
            type="info"
            size="small"
            effect="plain"
            class="ml-2"
          >
            <el-icon :size="11"><Lock /></el-icon>
            {{ logs.length }} 条历史
          </el-tag>
        </span>
        <div class="header-actions">
          <el-button
            v-if="logs.length > 0"
            size="small"
            text
            @click="emit('clear')"
          >
            清空
          </el-button>
          <el-tag
            v-if="isVerifying"
            type="info"
            size="small"
            effect="plain"
          >
            <el-icon
              class="rotating"
              :size="11"
            >
              <Loading />
            </el-icon>
            验证中
          </el-tag>
          <el-tag
            v-else
            type="success"
            size="small"
            effect="plain"
          >
            <el-icon :size="11">
              <Check />
            </el-icon>
            实时
          </el-tag>
        </div>
      </div>
    </template>
    <div
      v-if="logs.length === 0"
      class="verify-empty"
    >
      <el-icon :size="32">
        <Connection />
      </el-icon>
      <p>尚无操作记录。点击上方任意按钮 (触发/取消/重试/校验) 即可在此查看完整闭环链路。</p>
    </div>
    <div
      v-else
      class="verify-log-list"
    >
      <div
        v-for="log in logs"
        :key="log.id"
        class="verify-log-item"
        :class="`result-${log.result}`"
      >
        <div class="log-time">
          {{ logTime(log.timestamp) }}
          <span
            v-if="log.durationMs > 0"
            class="log-duration"
          >· {{ log.durationMs }}ms</span>
        </div>
        <div class="log-icon">
          <el-icon
            v-if="log.result === 'success'"
            :size="18"
            color="#16a34a"
          >
            <Check />
          </el-icon>
          <el-icon
            v-else-if="log.result === 'failed'"
            :size="18"
            color="#dc2626"
          >
            <Close />
          </el-icon>
          <el-icon
            v-else
            :size="18"
            color="#3b82f6"
            class="rotating"
          >
            <Loading />
          </el-icon>
        </div>
        <div class="log-content">
          <div class="log-action">
            {{ log.action }}
          </div>
          <div class="log-meta">
            <span class="log-endpoint"><code>{{ log.apiEndpoint }}</code></span>
            <span class="log-result-msg">{{ log.resultMessage }}</span>
          </div>
          <div class="log-verification">
            <el-icon
              :size="11"
              :color="log.result === 'failed' ? '#dc2626' : '#16a34a'"
            >
              <Check />
            </el-icon>
            <span class="log-verify-text">{{ log.verifiedBy }}</span>
            <span
              v-if="log.verifiedValue"
              class="log-verify-value"
            >→ {{ JSON.stringify(log.verifiedValue) }}</span>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.mb-4 { margin-bottom: var(--space-4); }
.ml-2 { margin-left: var(--space-2); }
.verify-log-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-bottom: 2px solid #0ea5e9;
}
.verify-empty {
  text-align: center;
  padding: var(--space-6);
  color: var(--muted-foreground);
}
.verify-empty p {
  margin: var(--space-2) 0 0 0;
  font-size: var(--font-size-sm);
}
.verify-log-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 360px;
  overflow-y: auto;
}
.verify-log-item {
  display: grid;
  grid-template-columns: 80px 28px 1fr;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
  font-size: var(--font-size-sm);
  background: var(--card);
  transition: background 0.2s;
}
.verify-log-item:hover { background: var(--muted); }
.verify-log-item:last-child { border-bottom: none; }
.verify-log-item.result-failed {
  background: linear-gradient(90deg, #fef2f2 0%, transparent 30%);
  border-left: 3px solid #dc2626;
}
.verify-log-item.result-success { border-left: 3px solid #16a34a; }
.verify-log-item.result-pending {
  border-left: 3px solid #3b82f6;
  background: linear-gradient(90deg, #eff6ff 0%, transparent 30%);
}
.log-time {
  font-size: 11px;
  color: var(--muted-foreground);
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', monospace);
  white-space: nowrap;
}
.log-duration {
  color: #6b7280;
  font-size: 10px;
  margin-left: 4px;
}
.log-icon {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 2px;
}
.log-content { min-width: 0; }
.log-action {
  font-weight: 600;
  color: var(--foreground);
  margin-bottom: 2px;
}
.log-meta {
  display: flex;
  gap: var(--space-3);
  font-size: 11px;
  color: var(--muted-foreground);
  margin-bottom: 2px;
  flex-wrap: wrap;
}
.log-endpoint code {
  background: var(--muted);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', monospace);
  font-size: 10px;
}
.log-result-msg { color: var(--foreground); font-size: 11px; }
.log-verification {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--foreground);
  flex-wrap: wrap;
  padding: 4px 6px;
  background: rgba(34, 197, 94, 0.08);
  border-radius: 4px;
  margin-top: 4px;
}
.log-verify-text { color: var(--foreground); font-weight: 500; }
.log-verify-value {
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', monospace);
  font-size: 10px;
  color: var(--muted-foreground);
  word-break: break-all;
}
.rotating { animation: rotate 1s linear infinite; }
@keyframes rotate {
  to { transform: rotate(360deg); }
}
</style>
