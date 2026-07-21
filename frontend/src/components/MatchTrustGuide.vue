<script setup lang="ts">
/**
 * MatchTrustGuide — explains what the match_score and trust_score mean
 * to a non-technical user. Phase 25 enhancement for §5.2 module D.
 *
 *   match_score (0-100): 你的技能对该岗位的覆盖度
 *   trust_score (0-100): 系统对该匹配结果的置信度
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
</script>

<template>
  <div class="trust-guide">
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
            系统对本次匹配结果的置信度 — 反映数据来源质量与覆盖度
          </div>
          <div
            class="trust-band-desc"
            :style="{ color: trustBand.color }"
          >
            {{ trustBand.description }}
          </div>
        </div>
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
</style>