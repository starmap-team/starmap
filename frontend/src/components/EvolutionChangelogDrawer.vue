<script setup lang="ts">
/**
 * Evolution changelog drawer — extracted from EvolutionDashboard.vue (audit M16)
 */
import type { ChangelogEntry } from '@/stores/evolution'
import type { ChangeType } from '@/types/evolution'

defineProps<{
  modelValue: boolean
  skillName: string
  data: ChangelogEntry[]
  loading: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

// ALIGN-04: ChangeType labels — matches backend diff_engine.py enum values
const changeTypeLabel: Record<ChangeType, string> = {
  added_required: '新增必需',
  added_preferred: '新增优先',
  removed: '移除技能',
  promoted: '升级',
  demoted: '降级',
  retained: '保留',
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :title="`${skillName} 演化历史`"
    size="400px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-loading="loading">
      <el-timeline v-if="data.length">
        <el-timeline-item
          v-for="(item, idx) in data"
          :key="idx"
          :timestamp="item.date ?? item.created_at ?? ''"
          placement="top"
        >
          <el-card
            shadow="never"
            class="changelog-card"
          >
            <div class="changelog-header">
              <el-tag
                size="small"
                effect="plain"
                type="primary"
              >
                {{ changeTypeLabel[item.change_type] ?? item.change_type ?? '变更' }}
              </el-tag>
            </div>
            <div
              v-if="item.old_proficiency || item.new_proficiency"
              class="changelog-detail"
            >
              <span class="changelog-label">熟练度:</span>
              <span>{{ item.old_proficiency ?? '-' }}</span>
              <span class="changelog-arrow">→</span>
              <span class="changelog-new">{{ item.new_proficiency ?? '-' }}</span>
            </div>
            <div
              v-if="item.old_requirement || item.new_requirement"
              class="changelog-detail"
            >
              <span class="changelog-label">需求等级:</span>
              <span>{{ item.old_requirement ?? '-' }}</span>
              <span class="changelog-arrow">→</span>
              <span class="changelog-new">{{ item.new_requirement ?? '-' }}</span>
            </div>
            <div
              v-if="item.description"
              class="changelog-detail"
            >
              <span>{{ item.description }}</span>
            </div>
            <div class="changelog-meta">
              <span
                v-if="item.trust_score"
                class="trust-meta"
              >
                信任度 {{ (item.trust_score * 100).toFixed(0) }}%
              </span>
              <span
                v-if="item.confidence"
                class="trust-meta"
              >
                置信度 {{ (item.confidence * 100).toFixed(0) }}%
              </span>
            </div>
          </el-card>
        </el-timeline-item>
      </el-timeline>
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
          ><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line
            x1="16"
            y1="13"
            x2="8"
            y2="13"
          /><line
            x1="16"
            y1="17"
            x2="8"
            y2="17"
          /><polyline points="10 9 9 9 8 9" /></svg>
        </div><p class="empty-text">
          该技能暂无变更记录
        </p>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.changelog-card { margin-bottom: 0; }
.changelog-header { margin-bottom: 6px; }
.changelog-detail {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--muted-foreground);
  margin-bottom: 4px;
}
.changelog-label { font-weight: 600; color: var(--foreground); }
.changelog-arrow { color: var(--muted-foreground); }
.changelog-new { color: var(--primary, #409eff); font-weight: 600; }
.changelog-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--muted-foreground);
  margin-top: 4px;
}
.trust-meta { opacity: 0.8; }
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 20px;
  color: var(--muted-foreground);
  text-align: center;
}
.empty-icon-wrapper { opacity: 0.4; }
.empty-text { font-size: 14px; margin: 0; }
</style>
