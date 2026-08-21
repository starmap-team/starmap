<script setup lang="ts">
/**
 * MatchTrustGuide — explains what the match_score and trust_score mean
 * to a non-technical user. enhancement for module D.
 *
 * match_score (0-100): 你的技能对该岗位的覆盖度
 * trust_score (0-100): 系统对该匹配结果的置信度
 *
 * Why both? A high match_score alone doesn't tell you whether the
 * comparison is reliable. A low-trust result might be missing key
 * skills the system didn't know about. Always read both together.
 */
import { computed } from 'vue'
import { CircleCheck, WarningFilled, QuestionFilled } from '@element-plus/icons-vue'

const props = defineProps<{
  matchScore?: number | null
  trustScore?: number | null
 //: 分数拆解（required_avg/bonus_avg/权重/inflated）— 用户可感知 match_score 构成
  scoreBreakdown?: {
    required_avg?: number
    bonus_avg?: number
    weight_required?: number
    weight_bonus?: number
    inflated?: boolean
  } | null
 //（ 强制规范）：后端 MatchResponse.note（如“岗位存在但暂无可用画像”）的呈现
  note?: string | null
}>()

interface ScoreBand {
  threshold: number
  label: string
  color: string
  description: string
}

function bandFor(score: number | null | undefined, bands: ScoreBand[]): ScoreBand {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return {
      threshold: 0,
      label: '未知',
      color: '#94a3b8',
      description: '尚未计算',
    }
  }
  for (const band of bands) {
    if (score >= band.threshold) return band
  }
  return bands[bands.length - 1]!
}

const matchBands: ScoreBand[] = [
  { threshold: 80, label: '优秀匹配', color: '#10b981', description: '你的技能高度覆盖岗位要求，可投递简历' },
  { threshold: 60, label: '良好匹配', color: '#3b82f6', description: '大部分技能匹配，仍有 1-2 项关键缺口' },
  { threshold: 40, label: '基础匹配', color: '#f59e0b', description: '基础胜任，建议补齐核心技能后再投递' },
  { threshold: 0,  label: '差距较大', color: '#ef4444', description: '需要系统性学习，建议参考学习路径' },
]

const trustBands: ScoreBand[] = [
  { threshold: 80, label: '高度可信', color: '#10b981', description: '基于多源数据交叉验证' },
  { threshold: 60, label: '基本可信', color: '#3b82f6', description: '建议人工复核岗位要求' },
  { threshold: 0,  label: '谨慎参考', color: '#f59e0b', description: '数据来源不足，结果仅供参考' },
]

const matchBand = computed(() => bandFor(props.matchScore != null ? Math.round((props.matchScore ?? 0) * 100) : null, matchBands))
const trustBand = computed(() => bandFor(props.trustScore != null ? Math.round((props.trustScore ?? 0) * 100) : null, trustBands))

//: 分数拆解计算 — 必备均值×权重 + 加分均值×权重
const pct = (v?: number) => v != null ? `${Math.round(v * 100)}%` : '—'
const breakdownLines = computed(() => {
  const b = props.scoreBreakdown
  if (!b) return []
  return [
    { label: '必备技能均值', value: pct(b.required_avg), weight: b.weight_required },
    { label: '加分技能均值', value: pct(b.bonus_avg), weight: b.weight_bonus },
  ]
})
//: trust_score 为空（Neo4j 不可用）时给出明确降级文案，而非裸「—」
const trustUnavailable = computed(() => props.trustScore == null || Number.isNaN(props.trustScore))
</script>

<template>
  <div class="trust-guide">
    <!--：呈现后端 MatchResponse.note（岗位存在但暂无可用画像/0 关系），避免 0 分被误读为“不会” -->
    <el-alert
      v-if="note"
      type="info"
      :closable="false"
      show-icon
      :title="'说明'"
    >
      {{ note }}
    </el-alert>
    <div
      class="trust-card"
      :style="{ borderLeft: `4px solid ${matchBand.color}` }"
    >
      <div class="trust-header">
        <span
          class="trust-icon"
          :style="{ color: matchBand.color }"
        >
          <el-icon :size="20"><CircleCheck /></el-icon>
        </span>
        <div class="trust-text">
          <div class="trust-title">
            匹配度: {{ matchScore != null ? Math.round((matchScore ?? 0) * 100) + '%' : '—' }}
            <el-tag
              :style="{ background: matchBand.color + '18', color: matchBand.color, border: 'none' }"
              size="small"
              effect="plain"
            >
              {{ matchBand.label }}
            </el-tag>
          </div>
          <div class="trust-desc">
            你的技能对该岗位的覆盖度 — 数值越高说明掌握越多岗位要求技能
          </div>
          <div
            class="trust-band-desc"
            :style="{ color: matchBand.color }"
          >
            {{ matchBand.description }}
          </div>
        </div>
      </div>
    </div>

    <div
      class="trust-card"
      :style="{ borderLeft: `4px solid ${trustBand.color}` }"
    >
      <div class="trust-header">
        <span
          class="trust-icon"
          :style="{ color: trustBand.color }"
        >
          <el-icon :size="20">
            <component :is="trustBand.color === '#f59e0b' ? QuestionFilled : WarningFilled" />
          </el-icon>
        </span>
        <div class="trust-text">
          <div class="trust-title">
            信任度: {{ trustScore != null ? Math.round((trustScore ?? 0) * 100) + '%' : '—' }}
            <el-tag
              :style="{ background: trustBand.color + '18', color: trustBand.color, border: 'none' }"
              size="small"
              effect="plain"
            >
              {{ trustBand.label }}
            </el-tag>
          </div>
          <div class="trust-desc">
            系统对本次匹配结果的置信度 — 命中技能中的最低信任度（瓶颈口径）
          </div>
          <div
            class="trust-band-desc"
            :style="{ color: trustBand.color }"
          >
            {{ trustBand.description }}
          </div>
          <!--: Neo4j 不可用时的明确降级提示 -->
          <div
            v-if="trustUnavailable"
            class="trust-unavailable"
          >
            信任度暂不可用（图谱服务未响应），其余结果不受影响
          </div>
        </div>
      </div>
    </div>

    <!--: 分数拆解 — 用户可感知 match_score 的构成 -->
    <div
      v-if="breakdownLines.length"
      class="breakdown-card"
    >
      <div class="breakdown-title">
        分数构成
        <el-tag
          v-if="props.scoreBreakdown?.inflated"
          type="warning"
          size="small"
          effect="plain"
          class="ml-2"
        >
          岗位要求存在通胀迹象，边缘必备项已按加分项处理
        </el-tag>
      </div>
      <div class="breakdown-row">
        <span class="breakdown-label">{{ breakdownLines[0].label }}</span>
        <span class="breakdown-value">{{ breakdownLines[0].value }}</span>
        <span class="breakdown-weight">× {{ breakdownLines[0].weight ?? 0.7 }}</span>
      </div>
      <div class="breakdown-row">
        <span class="breakdown-label">{{ breakdownLines[1].label }}</span>
        <span class="breakdown-value">{{ breakdownLines[1].value }}</span>
        <span class="breakdown-weight">× {{ breakdownLines[1].weight ?? 0.3 }}</span>
      </div>
      <div class="breakdown-formula">
        匹配度 = 必备均值 × 0.7 + 加分均值 × 0.3
      </div>
    </div>
  </div>
</template>

<style scoped>
.trust-guide {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.trust-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
}

.trust-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.trust-icon {
  flex-shrink: 0;
  padding-top: 2px;
}

.trust-text {
  flex: 1;
  min-width: 0;
}

.trust-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
}

.trust-desc {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

.trust-band-desc {
  margin-top: 4px;
  font-size: var(--font-size-sm);
  font-weight: 500;
}

/*: 信任度降级提示 */
.trust-unavailable {
  margin-top: 6px;
  font-size: 12px;
  color: var(--warning, #e6a23c);
}

/*: 分数拆解 */
.breakdown-card {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px dashed var(--border, #e4e7ed);
  border-radius: 8px;
  background: var(--card, #fff);
}
.breakdown-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.breakdown-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  margin-bottom: 4px;
}
.breakdown-label { color: var(--muted-foreground); flex: 1; }
.breakdown-value { font-weight: 600; }
.breakdown-weight { color: var(--muted-foreground); }
.breakdown-formula {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted-foreground);
}
</style>