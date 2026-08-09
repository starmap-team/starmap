<script setup lang="ts">
/**
 * JD 抽取页 — 粘贴 JD 文本，触发 LLM 抽取
 * 路由：/extract
 */
import { ref, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import MainLayout from '@/layouts/MainLayout.vue'
import { useJdStore } from '@/stores/jd'

const jd = useJdStore()

const jdText = ref('')
const charCount = computed(() => jdText.value.length)
const charLimit = 50000
const result = computed(() => jd.extractResult)
const loading = computed(() => jd.extractLoading)

// 透明化：识别是否使用本地/降级模型，前端给出相应提示（慢/精度较低）
const isDegradedModel = computed(() => {
  const m = (result.value?.model_used ?? '').toLowerCase()
  if (!m) return false
  return m.includes('fallback') || m.includes('qwen') || m.includes('ollama') || m.includes('local')
})

const extractProgress = ref(0)
const extractPhase = ref('')
let progressTimer: ReturnType<typeof setInterval> | null = null

async function handleExtract() {
  if (!jdText.value.trim()) {
    ElMessage.warning('请输入 JD 文本')
    return
  }
  // Phase 26 / BUG-004: clear any prior progress interval before
  // starting a new one. Without this, double-clicking "抽取" left
  // two intervals racing — the second one would advance the bar past
  // 85% and the random increments produced visually-jumpy progress.
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
  extractProgress.value = 0
  extractPhase.value = '正在调用 AI 分析 JD 文本...'
  progressTimer = setInterval(() => {
    if (extractProgress.value < 85) {
      extractProgress.value += Math.random() * 8
      if (extractProgress.value > 30) extractPhase.value = 'AI 正在提取技能要求...'
      if (extractProgress.value > 60) extractPhase.value = '正在进行技能归一化...'
    }
  }, 500)
  try {
    await jd.extractJd(jdText.value)
    extractProgress.value = 100
    extractPhase.value = '抽取完成！'
    ElMessage.success('抽取完成')
  } catch (e: unknown) {
    if (import.meta.env.DEV) console.error('[ExtractJD] Failed:', e)
    ElMessage.error(e instanceof Error ? e.message : '抽取失败')
    extractPhase.value = '抽取失败'
  } finally {
    if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
  }
}

function handleClear() {
  jdText.value = ''
  jd.clearResult()
}

onUnmounted(() => {
  if (progressTimer) clearInterval(progressTimer)
})
</script>

<template>
  <MainLayout>
    <div class="extract-page animate-fade-in">
      <div class="page-header">
        <h2>JD 智能抽取</h2>
        <p class="subtitle">
          粘贴职位描述文本，AI 自动提取技能要求
        </p>
      </div>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header-row">
                <span>JD 原文</span>
                <el-button
                  size="small"
                  @click="handleClear"
                >
                  清空
                </el-button>
              </div>
            </template>
            <el-input
              v-model="jdText"
              type="textarea"
              :rows="15"
              placeholder="粘贴职位描述文本..."
              maxlength="50000"
              show-word-limit
            />
            <div class="input-footer">
              <span :class="['char-count', charCount > charLimit * 0.9 ? 'char-warn' : '']">
                {{ charCount }} / {{ charLimit }} 字
              </span>
            </div>
            <div class="extract-action">
              <el-button
                type="primary"
                :loading="loading"
                @click="handleExtract"
              >
                开始抽取
              </el-button>
            </div>
          
            <!-- Progress indicator for long LLM wait -->
            <div
              v-if="loading"
              class="extract-progress"
            >
              <el-progress
                :percentage="Math.round(extractProgress)"
                :stroke-width="8"
                :color="extractProgress >= 100 ? 'var(--success)' : 'var(--primary)'"
              />
              <p class="extract-phase">
                {{ extractPhase }}
              </p>
            </div>
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card v-loading="loading">
            <template #header>
              抽取结果
            </template>
            <div v-if="result">
              <el-descriptions
                :column="1"
                border
                size="small"
              >
                <el-descriptions-item label="职位名称">
                  {{ result.position_name || result.job_title || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="经验要求">
                  {{ result.experience_required ?? result.experience_years ?? '-' }} 年
                </el-descriptions-item>
                <el-descriptions-item label="学历要求">
                  {{ result.education_required ?? result.education ?? '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="置信度">
                  <el-progress
                    :percentage="Math.round((result.confidence ?? 0) * 100)"
                    :stroke-width="10"
                  />
                </el-descriptions-item>
              </el-descriptions>

              <div
                v-if="result.model_used"
                class="model-used-note"
              >
                <el-tag
                  :type="isDegradedModel ? 'warning' : 'info'"
                  effect="plain"
                  size="small"
                >
                  模型
                </el-tag>
                <span class="model-used-text">
                  {{ result.model_used }}
                </span>
                <span
                  v-if="isDegradedModel"
                  class="degraded-hint"
                >（本地降级模型，处理较慢）</span>
              </div>

              <h4 class="result-section-title">
                必备技能
              </h4>
              <div class="skill-tags-row">
                <el-tag
                  v-for="s in (result.required_skills ?? [])"
                  :key="s.skill ?? s.name ?? s"
                  type="danger"
                  effect="plain"
                >
                  {{ s.skill ?? s.name ?? s }}
                </el-tag>
                <span
                  v-if="!(result.required_skills?.length)"
                  class="starmap-empty--sm"
                >无</span>
              </div>

              <h4 class="result-section-title">
                加分技能
              </h4>
              <div class="skill-tags-row">
                <el-tag
                  v-for="s in (result.preferred_skills ?? [])"
                  :key="s.skill ?? s.name ?? s"
                  type="warning"
                  effect="plain"
                >
                  {{ s.skill ?? s.name ?? s }}
                </el-tag>
                <span
                  v-if="!(result.preferred_skills?.length)"
                  class="starmap-empty--sm"
                >无</span>
              </div>

              <h4 class="result-section-title">
                工具 / 技术栈
              </h4>
              <div class="skill-tags-row">
                <el-tag
                  v-for="s in (result.tools ?? [])"
                  :key="s.skill ?? s.name ?? s"
                  type="info"
                  effect="plain"
                >
                  {{ s.skill ?? s.name ?? s }}
                </el-tag>
                <span
                  v-if="!(result.tools?.length)"
                  class="starmap-empty--sm"
                >无</span>
              </div>

              <h4 class="result-section-title">
                岗位演进方向
              </h4>
              <div class="skill-tags-row">
                <el-tag
                  v-for="p in (result.evolves_to ?? [])"
                  :key="p"
                  type="primary"
                  effect="plain"
                >
                  {{ p }}
                </el-tag>
                <span
                  v-if="!(result.evolves_to?.length)"
                  class="starmap-empty--sm"
                >无</span>
              </div>

              <h4 class="result-section-title">
                幻觉防控
              </h4>
              <div
                v-if="result.hallucination_score != null"
                class="hc-row"
              >
                <span class="hc-label">幻觉评分:</span>
                <el-tag
                  :type="(result.hallucination_score ?? 0) > 0.5 ? 'danger' : 'success'"
                  effect="plain"
                >
                  {{ ((result.hallucination_score ?? 0) * 100).toFixed(0) }}%
                </el-tag>
              </div>
              <div class="hc-row">
                <span class="hc-label">幻觉技能:</span>
                <div class="skill-tags-row">
                  <el-tag
                    v-for="s in (result.hallucinated_skills ?? [])"
                    :key="s"
                    type="danger"
                    effect="dark"
                  >
                    {{ s }}
                  </el-tag>
                  <span
                    v-if="!(result.hallucinated_skills?.length)"
                    class="starmap-empty--sm"
                  >无</span>
                </div>
              </div>
              <div class="hc-row">
                <span class="hc-label">缺失技能:</span>
                <div class="skill-tags-row">
                  <el-tag
                    v-for="s in (result.missing_skills ?? [])"
                    :key="s"
                    type="warning"
                    effect="plain"
                  >
                    {{ s }}
                  </el-tag>
                  <span
                    v-if="!(result.missing_skills?.length)"
                    class="starmap-empty--sm"
                  >无</span>
                </div>
              </div>
              <div
                v-if="(result.issues?.length)"
                class="hc-issues"
              >
                <span class="hc-label">问题:</span>
                <ul class="hc-issues-list">
                  <li
                    v-for="(issue, idx) in (result.issues ?? [])"
                    :key="idx"
                  >
                    {{ issue }}
                  </li>
                </ul>
              </div>

              <h4 class="result-section-title">
                学习资源
              </h4>
              <div
                v-if="(result.learning_resources?.length)"
                class="skill-tags-row"
              >
                <el-tag
                  v-for="(r, idx) in (result.learning_resources ?? [])"
                  :key="idx"
                  type="success"
                  effect="plain"
                  class="learning-resource"
                >
                  {{ r.title }}
                  <span v-if="r.type">({{ r.type }})</span>
                </el-tag>
              </div>
              <span
                v-else
                class="starmap-empty--sm"
              >无</span>

              <h4 class="result-section-title">
                标准化结果
              </h4>
              <el-table
                :data="result.normalized_skills ?? []"
                size="small"
                stripe
                max-height="200"
                empty-text="暂无数据"
              >
                <el-table-column
                  prop="original"
                  label="原始"
                />
                <el-table-column
                  prop="normalized"
                  label="标准化"
                />
                <el-table-column
                  prop="method"
                  label="方法"
                  width="100"
                />
                <el-table-column
                  label="置信度"
                  width="80"
                >
                  <template #default="{ row }">
                    {{ ((row.confidence ?? 0) * 100).toFixed(0) }}%
                  </template>
                </el-table-column>
              </el-table>
            </div>
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
              </div><p class="starmap-empty--sm">
                输入 JD 文本开始抽取
              </p><p class="empty-hint-text">
                粘贴职位描述后点击「开始抽取」
              </p>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </MainLayout>
</template>

<style scoped>
.extract-page { max-width: 1200px; }
.page-header { margin-bottom: var(--space-5); }
.page-header h2 { margin: 0 0 var(--space-1); font-size: var(--font-size-2xl); font-weight: 800; letter-spacing: var(--tracking-tight); color: var(--foreground); }
.subtitle { color: var(--muted-foreground); margin: 0; font-size: var(--font-size-base); }
.input-footer { display: flex; justify-content: flex-end; margin-top: var(--space-1); }
.char-count { font-size: var(--font-size-xs); color: var(--muted-foreground); }
.char-warn { color: var(--warning); }

.card-header-row { display: flex; justify-content: space-between; align-items: center; }
.extract-action { margin-top: var(--space-3); text-align: right; }
.extract-progress { margin-top: var(--space-4); }
.extract-phase { text-align: center; color: var(--muted-foreground); font-size: var(--font-size-sm); margin-top: var(--space-2); }
.result-section-title { font-size: var(--font-size-xs); font-weight: 600; color: var(--muted-foreground); text-transform: uppercase; letter-spacing: 0.06em; margin: var(--space-5) 0 var(--space-3); }
.result-section-title:not(:first-child) { margin-top: var(--space-3); }
.skill-tags-row { display: flex; flex-wrap: wrap; gap: var(--space-1); }

/* ── 模型透明化提示 ── */
.model-used-note { display: flex; align-items: center; gap: var(--space-2); margin-top: var(--space-3); }
.model-used-text { font-size: var(--font-size-sm); color: var(--muted-foreground); font-family: var(--font-mono); }
.degraded-hint { font-size: var(--font-size-xs); color: var(--warning); }

/* ── 幻觉防控信号 ── */
.hc-row { display: flex; align-items: flex-start; gap: var(--space-2); margin-bottom: var(--space-2); }
.hc-label { flex-shrink: 0; font-size: var(--font-size-sm); font-weight: 600; color: var(--muted-foreground); min-width: 68px; line-height: 24px; }
.hc-issues { margin-top: var(--space-1); }
.hc-issues-list { margin: 0; padding-left: var(--space-5); color: var(--muted-foreground); font-size: var(--font-size-sm); }
.hc-issues-list li { margin-bottom: var(--space-1); }
.learning-resource { margin-bottom: var(--space-1); }


/* ── Custom Empty State ── */
.custom-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) var(--space-6);
  text-align: center;
}
.empty-icon-wrapper {
  color: var(--muted-foreground);
  opacity: 0.4;
  margin-bottom: var(--space-4);
}
.empty-text {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}
.empty-hint-text {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: var(--space-1) 0 0;
}
.empty-slot {
  margin-top: var(--space-4);
}
</style>