<script setup lang="ts">
/**
 * JD 抽取页 — 粘贴 JD 文本，触发 LLM 抽取
 * 路由：/extract
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import MainLayout from '@/layouts/MainLayout.vue'
import request from '@/api/request'

const jdText = ref('')
const charCount = computed(() => jdText.value.length)
const charLimit = 10000
const loading = ref(false)
const result = ref<any>(null)

const extractProgress = ref(0)
const extractPhase = ref('')
let progressTimer: ReturnType<typeof setInterval> | null = null

async function handleExtract() {
  if (!jdText.value.trim()) {
    ElMessage.warning('请输入 JD 文本')
    return
  }
  loading.value = true
  result.value = null
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
    const data = await request.post('/extract/jd', {
      jd_content: jdText.value,
    }, {
      timeout: 120000,
    })
    extractProgress.value = 100
    extractPhase.value = '抽取完成！'
    result.value = data
    ElMessage.success('抽取完成')
  } catch (e: any) {
    console.error('[ExtractJD] Failed:', e)
    ElMessage.error(e?.message ?? '抽取失败')
    extractPhase.value = '抽取失败'
  } finally {
    if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
    loading.value = false
  }
}

function handleClear() {
  jdText.value = ''
  result.value = null
}
</script>

<template>
  <MainLayout>
    <div class="extract-page animate-fade-in">
      <div class="page-header">
        <h2>JD 智能抽取</h2>
        <p class="subtitle">粘贴职位描述文本，AI 自动提取技能要求</p>
      </div>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header-row">
                <span>JD 原文</span>
                <el-button size="small" @click="handleClear">清空</el-button>
              </div>
            </template>
            <el-input
              v-model="jdText"
              type="textarea"
              :rows="15"
              placeholder="粘贴职位描述文本..."
              maxlength="10000"
              show-word-limit
            />
            <div class="input-footer">
              <span :class="['char-count', charCount > charLimit * 0.9 ? 'char-warn' : '']">
                {{ charCount }} / {{ charLimit }} 字
              </span>
            </div>
            <div class="extract-action">
              <el-button type="primary" :loading="loading" @click="handleExtract">
                开始抽取
              </el-button>
            </div>
          
            <!-- Progress indicator for long LLM wait -->
            <div v-if="loading" class="extract-progress">
              <el-progress :percentage="Math.round(extractProgress)" :stroke-width="8" :color="extractProgress >= 100 ? '#67c23a' : '#409eff'" />
              <p class="extract-phase">{{ extractPhase }}</p>
            </div>
            </el-card>
        </el-col>

        <el-col :span="12">
          <el-card v-loading="loading">
            <template #header>抽取结果</template>
            <div v-if="result">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="职位名称">
                  {{ result.position_name ?? result.job_title ?? '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="经验要求">
                  {{ result.experience_required ?? result.experience_years ?? '-' }} 年
                </el-descriptions-item>
                <el-descriptions-item label="学历要求">
                  {{ result.education_required ?? result.education ?? '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="置信度">
                  <el-progress :percentage="Math.round((result.confidence ?? 0) * 100)" :stroke-width="10" />
                </el-descriptions-item>
              </el-descriptions>

              <h4 class="result-section-title">必备技能</h4>
              <div class="skill-tags-row">
                <el-tag v-for="s in (result.required_skills ?? [])" :key="s.skill ?? s.name ?? s" type="danger" effect="plain">
                  {{ s.skill ?? s.name ?? s }}
                </el-tag>
                <span v-if="!(result.required_skills?.length)" class="empty-text">无</span>
              </div>

              <h4 class="result-section-title">加分技能</h4>
              <div class="skill-tags-row">
                <el-tag v-for="s in (result.preferred_skills ?? [])" :key="s.skill ?? s.name ?? s" type="warning" effect="plain">
                  {{ s.skill ?? s.name ?? s }}
                </el-tag>
                <span v-if="!(result.preferred_skills?.length)" class="empty-text">无</span>
              </div>

              <h4 class="result-section-title">标准化结果</h4>
              <el-table :data="result.normalized_skills ?? []" size="small" stripe max-height="200">
                <el-table-column prop="original" label="原始" />
                <el-table-column prop="normalized" label="标准化" />
                <el-table-column prop="method" label="方法" width="100" />
                <el-table-column label="置信度" width="80">
                  <template #default="{ row }">
                    {{ ((row.confidence ?? 0) * 100).toFixed(0) }}%
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <el-empty v-else description="请在左侧输入 JD 文本并点击抽取" />
          </el-card>
        </el-col>
      </el-row>
    </div>
  </MainLayout>
</template>

<style scoped>
.extract-page { max-width: 1200px; }
.page-header { margin-bottom: var(--space-5); }
.page-header h2 { margin: 0 0 4px; font-size: var(--font-size-2xl); }
.subtitle { color: var(--muted-foreground); margin: 0; font-size: var(--font-size-base); }
.input-footer { display: flex; justify-content: flex-end; margin-top: var(--space-1); }
.char-count { font-size: var(--font-size-xs); color: var(--muted-foreground); }
.char-warn { color: var(--warning); }

.card-header-row { display: flex; justify-content: space-between; align-items: center; }
.extract-action { margin-top: var(--space-3); text-align: right; }
.extract-progress { margin-top: var(--space-4); }
.extract-phase { text-align: center; color: var(--muted-foreground); font-size: var(--font-size-sm); margin-top: var(--space-2); }
.result-section-title { font-size: var(--font-size-base); font-weight: 600; color: var(--foreground); margin: var(--space-4) 0 var(--space-2); }
.result-section-title:not(:first-child) { margin-top: var(--space-3); }
.skill-tags-row { display: flex; flex-wrap: wrap; gap: var(--space-1); }
.empty-text { color: var(--muted-foreground); font-size: var(--font-size-sm); }
</style>