<script setup lang="ts">
/**
 * Evolution changelog drawer — extracted from EvolutionDashboard.vue (audit)
 */
import { computed } from 'vue'
import type { ChangelogEntry } from '@/stores/evolution'
import type { ChangeType } from '@/types/evolution'

const props = withDefaults(defineProps<{
  modelValue: boolean
  skillName: string
  data: ChangelogEntry[]
  loading: boolean
 // 10-03 : 证据区展开开关 — 默认 false 折叠不打扰
  evidenceOpen?: boolean
}>(), {
  evidenceOpen: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

//: el-collapse active names derived from the evidence drawer switch
const evidenceActive = computed(() => (props.evidenceOpen ? ['evidence'] : []))

//: ChangeType labels — matches backend diff_engine.py enum values
const changeTypeLabel: Record<ChangeType, string> = {
  added_required: '新增必需',
  added_preferred: '新增优先',
  removed: '移除技能',
  promoted: '升级',
  demoted: '降级',
  retained: '保留',
}

// 10-03 : trust badge color tiers — >=0.8 success / >=0.6 warning / <0.6 danger
function trustTagType(score?: number): 'success' | 'warning' | 'danger' | 'info' {
  if (score == null) return 'info'
  if (score >= 0.8) return 'success'
  if (score >= 0.6) return 'warning'
  return 'danger'
}

// 10-03 : evidence_json → displayable {label, value} list (fixed keys only,
// no raw JSON export). Evidence written by the pipeline (orchestrator + factors),
// not user-controllable (T-10-11).
interface EvidenceField { label: string; value: string }

function evidenceFields(evidence?: Record<string, unknown>): EvidenceField[] {
  if (!evidence || typeof evidence !== 'object') return []
  const out: EvidenceField[] = []
  if (evidence.source_count != null) out.push({ label: '源计数', value: String(evidence.source_count) })
  if (evidence.mention_count_old != null) out.push({ label: '提及（旧）', value: String(evidence.mention_count_old) })
  if (evidence.mention_count_new != null) out.push({ label: '提及（新）', value: String(evidence.mention_count_new) })
  if (evidence.change_type) out.push({ label: '变更类型', value: String(evidence.change_type) })
  const factors = (evidence.factors && typeof evidence.factors === 'object') ? evidence.factors as Record<string, unknown> : undefined
  if (factors?.stability != null) out.push({ label: '稳定性因子', value: String(factors.stability) })
  return out
}

const hasEvidence = (evidence?: Record<string, unknown>): boolean => evidenceFields(evidence).length > 0
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
              <el-tag
                v-if="item.trust_score"
                :type="trustTagType(item.trust_score)"
                size="small"
                effect="light"
                :title="`演化变更的 TrustScorer 评分（与 Neo4j Skill.trust_score 是不同维度）`"
              >
                <!-- D5 fix: rename to "变更置信度" — this value comes from
                     TrustScorer (source/stability/type factors blended for a
                     single change), NOT Neo4j Skill.trust_score (the per-skill
                     admin "平均信任度" KPI). Same name was misleading users. -->
                变更置信度 {{ (item.trust_score * 100).toFixed(0) }}%
              </el-tag>
              <span
                v-if="item.confidence"
                class="trust-meta"
              >
                置信度 {{ (item.confidence * 100).toFixed(0) }}%
              </span>
              <!-- 10-03 (D-06 透传): 回写状态小标签（镜像 ExtractJD model_used 透传样式） -->
              <el-tag
                v-if="item.written_back"
                type="info"
                size="small"
                effect="plain"
                class="written-back-tag"
              >
                已回写
              </el-tag>
            </div>
            <!-- 10-03 (D-09): 可折叠证据区 — 默认折叠不打扰 -->
            <el-collapse
              :model-value="evidenceActive"
              class="evidence-collapse"
            >
              <el-collapse-item
                :title="`证据（${evidenceFields(item.evidence_json).length}）`"
                name="evidence"
              >
                <template #default>
                  <template v-if="hasEvidence(item.evidence_json)">
                    <div
                      v-for="f in evidenceFields(item.evidence_json)"
                      :key="f.label"
                      class="evidence-row"
                    >
                      <span class="changelog-label">{{ f.label }}</span>
                      <span>{{ f.value }}</span>
                    </div>
                  </template>
                  <div
                    v-else
                    class="evidence-empty"
                  >
                    暂无证据
                  </div>
                </template>
              </el-collapse-item>
            </el-collapse>
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
        </p><p class="empty-hint">
          演化分析窗口内未检测到该技能的变更（新增/升降级/移除）。可触发演化分析后刷新查看。
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
.written-back-tag { margin-left: auto; }
.evidence-collapse { margin-top: 8px; }
.evidence-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: var(--muted-foreground);
  padding: 2px 0;
}
.evidence-empty {
  font-size: 12px;
  color: var(--muted-foreground);
  opacity: 0.7;
  padding: 4px 0;
}
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
.empty-hint { font-size: 12px; margin: 0; color: var(--muted-foreground); }
</style>
