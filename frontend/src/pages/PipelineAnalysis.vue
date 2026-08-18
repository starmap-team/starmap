<template>
  <MainLayout>
    <div class="pipeline-analysis">
      <div class="page-header">
        <h2>求职者分析</h2>
        <p class="subtitle">
          上传简历，获得完整的技能评估、岗位匹配和学习路径推荐
        </p>
      </div>

      <!-- Step 1: 上传区域 -->
      <el-card
        v-if="!store.loading && !store.result"
        class="upload-card"
      >
        <el-upload
          drag
          :auto-upload="false"
          :on-change="handleFileChange"
          :limit="1"
          accept=".pdf,.docx,.doc"
        >
          <el-icon class="el-icon--upload">
            <UploadFilled />
          </el-icon>
          <div class="el-upload__text">
            拖拽简历到此处，或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              支持 PDF / DOCX / DOC 格式（≤10MB）
            </div>
          </template>
        </el-upload>

        <div class="actions">
          <el-button
            type="primary"
            :disabled="!selectedFile"
            @click="startAnalysis"
          >
            开始分析
          </el-button>
        </div>
      </el-card>

      <!-- Step 2: 进度 -->
      <el-card
        v-if="store.loading"
        class="progress-card"
      >
        <h3>分析中...</h3>
        <el-steps
          :active="activeStep"
          finish-status="success"
          align-center
        >
          <el-step title="简历解析" />
          <el-step title="技能提取" />
          <el-step title="岗位匹配" />
          <el-step title="学习路径" />
          <el-step title="岗位推荐" />
        </el-steps>
        <div class="progress-log">
          <div
            v-for="(p, i) in store.progress"
            :key="i"
            class="log-item"
          >
            <el-tag
              :type="statusType(p.status)"
              size="small"
            >
              {{ p.step }}
            </el-tag>
            <span>{{ statusText(p.status) }}</span>
          </div>
        </div>

        <!--: 逐步可视化核验面板 -->
        <div
          v-if="store.stepOutputs.length"
          class="step-verify-section"
        >
          <h4 class="verify-title">
            <el-icon><Checked /></el-icon>
            步骤核验
          </h4>
          <el-collapse accordion>
            <el-collapse-item
              v-for="output in store.stepOutputs"
              :key="output.step"
            >
              <template #title>
                <div class="verify-step-header">
                  <el-tag
                    :type="output.verification.passed ? 'success' : 'danger'"
                    size="small"
                    effect="plain"
                  >
                    {{ output.verification.passed ? '通过' : '未通过' }}
                  </el-tag>
                  <span class="verify-step-name">{{ output.display_name }}</span>
                  <span
                    v-if="output.status === 'error'"
                    class="verify-error-hint"
                  >{{ output.error }}</span>
                </div>
              </template>
              <!-- 验证检查项 -->
              <div class="verify-checks">
                <div
                  v-for="(check, ci) in output.verification.checks"
                  :key="ci"
                  class="verify-check-item"
                >
                  <el-icon
                    :class="check.ok ? 'check-ok' : 'check-fail'"
                    :size="16"
                  >
                    <CircleCheck v-if="check.ok" />
                    <CircleClose v-else />
                  </el-icon>
                  <div class="check-content">
                    <span class="check-label">{{ check.check }}</span>
                    <span class="check-detail">{{ check.detail }}</span>
                  </div>
                </div>
              </div>
              <!-- 数据样本 -->
              <div
                v-if="output.samples.length"
                class="verify-samples"
              >
                <div
                  v-for="(sample, si) in output.samples"
                  :key="si"
                  class="sample-block"
                >
                  <div class="sample-label">
                    {{ sample.label ?? sample.name ?? sample.position ?? '样本' }}
                  </div>
                  <pre class="sample-value">{{ formatSample(sample.value ?? sample) }}</pre>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-card>

      <!-- Step 3: 结果 -->
      <el-card
        v-if="store.result"
        class="result-card"
      >
        <template #header>
          <div class="result-header">
            <span>分析结果</span>
            <div>
              <el-button
                text
                type="primary"
                @click="viewInGraph"
              >
                查看岗位详情
              </el-button>
              <el-button
                text
                type="primary"
                @click="exportJSON"
              >
                导出 JSON
              </el-button>
              <el-button
                text
                @click="store.reset()"
              >
                重新分析
              </el-button>
            </div>
          </div>
        </template>

        <!-- 4个核心问题卡片 -->
        <el-row
          :gutter="16"
          class="kpi-row"
        >
          <el-col :span="6">
            <el-statistic
              title="提取技能"
              :value="store.result.extracted_skills.length"
              suffix="项"
            />
          </el-col>
          <el-col :span="6">
            <el-statistic
              title="匹配岗位"
              :value="store.result.top_matches.length"
              suffix="个"
            />
          </el-col>
          <el-col :span="6">
            <el-statistic
              title="推荐岗位"
              :value="store.result.recommended_positions.length"
              suffix="个"
            />
          </el-col>
          <el-col :span="6">
            <el-statistic
              title="技能差距"
              :value="store.result.skill_gaps.filter(g => g.gap_level !== '已掌握').length"
              suffix="项"
            />
          </el-col>
        </el-row>

        <!-- 问题1: 适合什么岗位 -->
        <h3>🎯 我适合什么岗位？</h3>
        <el-table
          :data="store.result.top_matches.slice(0, 5)"
          stripe
          size="small"
          empty-text="暂无数据"
        >
          <el-table-column
            prop="position"
            label="岗位"
          />
          <el-table-column
            prop="match_score"
            label="匹配度"
            width="100"
          >
            <template #default="{ row }">
              <el-progress
                :percentage="Math.round(row.match_score * 100)"
                :stroke-width="12"
              />
            </template>
          </el-table-column>
          <el-table-column
            prop="assessment"
            label="评估"
          />
          <el-table-column
            prop="gap_count"
            label="差距数"
            width="80"
          />
        </el-table>

        <!-- 问题2: 缺什么技能 -->
        <h3>📋 我缺什么技能？</h3>
        <el-table
          :data="store.result.skill_gaps.filter(g => g.gap_level !== '已掌握').slice(0, 10)"
          stripe
          size="small"
          empty-text="暂无数据"
        >
          <el-table-column
            prop="skill"
            label="技能"
          />
          <el-table-column
            label="重要性"
            width="100"
          >
            <template #default="{ row }">
              <!-- P4 fix: importance 中文化（required=必备 / bonus=加分） -->
              <el-tag
                :type="row.importance === 'required' ? 'danger' : 'info'"
                size="small"
              >
                {{ row.importance === 'required' ? '必备' : '加分' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="gap_level"
            label="差距程度"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="row.gap_level === '完全缺失' ? 'danger' : 'warning'"
                size="small"
              >
                {{ row.gap_level }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="score"
            label="掌握度"
            width="100"
          >
            <template #default="{ row }">
              <!-- P4 fix: score 缺失/未定义时显示 — 而非 NaN%（后端已补字段，双保险） -->
              {{ typeof row.score === 'number' && Number.isFinite(row.score) ? Math.round(row.score * 100) + '%' : '—' }}
            </template>
          </el-table-column>
        </el-table>

        <!-- 问题3: 该学什么 -->
        <h3>📚 我该学什么？</h3>
        <div v-if="store.result.learning_path_summary.length">
          <div
            v-for="(path, i) in store.result.learning_path_summary.slice(0, 3)"
            :key="i"
            class="learning-path"
          >
            <el-tag
              v-for="(step, j) in path"
              :key="j"
              :type="j === 0 ? 'danger' : j === path.length - 1 ? 'success' : ''"
              class="path-step"
            >
              {{ step }}
            </el-tag>
          </div>
        </div>
        <el-empty
          v-else
          description="暂无学习路径数据"
        />

        <!-- 学习资源推荐 -->
        <h3 v-if="gapsWithResources.length">
          📖 推荐学习资源
        </h3>
        <div
          v-for="gap in gapsWithResources"
          :key="gap.skill"
          class="resource-section"
        >
          <h4>
            {{ gap.skill }} <el-tag
              type="danger"
              size="small"
            >
              {{ gap.gap_level }}
            </el-tag>
          </h4>
          <ul class="resource-list">
            <li
              v-for="(res, ri) in gap.learning_resources"
              :key="ri"
            >
              <a
                v-if="res.url"
                :href="res.url"
                target="_blank"
                rel="noopener noreferrer"
              >{{ res.name }}</a>
              <span v-else>{{ res.name }}</span>
              <el-tag
                v-if="res.type"
                size="small"
                type="info"
                class="resource-type"
              >
                {{ res.type }}
              </el-tag>
            </li>
          </ul>
        </div>

        <!-- 问题4: 推荐岗位 -->
        <h3>🚀 推荐岗位</h3>
        <el-table
          :data="store.result.recommended_positions.slice(0, 5)"
          stripe
          size="small"
          empty-text="暂无数据"
        >
          <el-table-column
            prop="position"
            label="岗位"
          />
          <el-table-column
            prop="score"
            label="综合得分"
            width="100"
          >
            <template #default="{ row }">
              {{ (row.score * 100).toFixed(1) }}%
            </template>
          </el-table-column>
          <el-table-column
            prop="match_score"
            label="匹配度"
            width="100"
          >
            <template #default="{ row }">
              {{ (row.match_score * 100).toFixed(1) }}%
            </template>
          </el-table-column>
          <el-table-column
            prop="developability"
            label="可发展性"
            width="100"
          >
            <template #default="{ row }">
              {{ (row.developability * 100).toFixed(1) }}%
            </template>
          </el-table-column>
        </el-table>

        <!-- 错误提示 -->
        <el-alert
          v-if="store.result.errors.length"
          :title="`分析过程中有 ${store.result.errors.length} 个警告`"
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 16px"
        >
          <ul>
            <li
              v-for="(e, i) in store.result.errors"
              :key="i"
            >
              {{ e }}
            </li>
          </ul>
        </el-alert>
      </el-card>

      <!-- 错误提示 -->
      <el-alert
        v-if="store.error"
        :title="store.error"
        type="error"
        show-icon
        style="margin-top: 16px"
      />
    </div>
  </MainLayout>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled, Checked, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useJobseekerStore } from '@/stores/jobseeker'

const router = useRouter()

const store = useJobseekerStore()
const selectedFile = ref<File | null>(null)

/** 有学习资源的技能差距列表。 */
const gapsWithResources = computed(() => {
  if (!store.result) return []
  return store.result.skill_gaps
    .filter(g => g.gap_level !== '已掌握' && g.learning_resources?.length)
    .slice(0, 5)
})

const stepMap: Record<string, number> = {
  resume_parse: 0,
  skill_extract: 1,
  match: 2,
  learning_path: 3,
  recommend: 4,
  complete: 5,  // P1 fix: complete 事件使 el-steps 全部完成（active=5 表示 5/5）
}

const activeStep = computed(() => {
  if (!store.currentStep) return 0
  return (stepMap[store.currentStep] ?? 0) + 1
})

function handleFileChange(file: { raw: File }) {
  selectedFile.value = file.raw
}

/** P3 fix ( 求职者分析): 前端文件校验 + 防重复点击。 */
function startAnalysis() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择简历文件')
    return
  }
  if (store.loading) return  // 防重复提交
  const f = selectedFile.value
  const okExt = /\.(pdf|docx?)$/i.test(f.name)
  const okType = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'].includes(f.type)
  if (!okExt && !okType) {
    ElMessage.error('仅支持 PDF / DOCX / DOC 格式')
    return
  }
  if (f.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 10MB')
    return
  }
  store.analyzeResume(f)
}

function viewInGraph() {
  if (!store.result?.top_matches?.length) return
  const topPosition = store.result.top_matches[0].position
 // ponytail: 原实现跳 '/' 带 highlight 参数，但 Home.vue 从不消费该参数（点击无任何效果）；
 // 直接跳转真实存在的岗位详情页，展示该岗位技能画像
  router.push(`/position/${encodeURIComponent(topPosition)}`)
}

function exportJSON() {
  if (!store.result) return
  const blob = new Blob([JSON.stringify(store.result, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `starmap-analysis-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function statusType(status: string) {
  if (status === 'done') return 'success'
  if (status === 'error' || status === 'timeout') return 'danger'
  return ''
}

function statusText(status: string) {
  if (status === 'running') return '执行中...'
  if (status === 'done') return '完成'
  if (status === 'timeout') return '超时'
  if (status === 'error') return '失败'
  return status
}

/**: 格式化样本数据为可读文本（兼容后端多样样本结构） */
function formatSample(value: unknown): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
 // 如果是对象数组，格式化为表格形式
    if (value.length > 0 && typeof value[0] === 'object') {
      return JSON.stringify(value, null, 2)
    }
    return value.join(', ')
  }
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value, null, 2)
  }
  return String(value ?? '')
}
</script>

<style scoped>
.pipeline-analysis {
  max-width: 960px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: var(--space-6);
}

.page-header h2 {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  color: var(--foreground);
  margin: 0 0 var(--space-2);
}

.subtitle {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
  margin: 0;
}

.upload-card {
  text-align: center;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
}

.actions {
  margin-top: var(--space-4);
}

.progress-card {
  text-align: center;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
}

.progress-log {
  margin-top: var(--space-6);
  text-align: left;
}

.log-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) 0;
}

.kpi-row {
  margin-bottom: var(--space-6);
}

.result-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

h3 {
  margin: var(--space-6) 0 var(--space-3);
  color: var(--foreground);
  font-size: var(--font-size-lg);
  font-weight: 600;
}

h4 {
  margin: 0 0 var(--space-2);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.learning-path {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  flex-wrap: wrap;
 /* P4 fix: 多条路径间留视觉分隔，避免标签平铺误读为一条长路径 */
  border-bottom: 1px dashed var(--border);
}
.learning-path:last-child {
  border-bottom: none;
}

.path-step {
  font-size: 13px;
}

.resource-section {
  margin: var(--space-2) 0 var(--space-4);
  padding: var(--space-4);
  background: var(--muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.resource-list {
  margin: 0;
  padding-left: var(--space-5);
}

.resource-list li {
  padding: var(--space-1) 0;
}

.resource-list a {
  color: var(--primary);
  text-decoration: none;
  transition: opacity var(--duration-fast);
}

.resource-list a:hover {
  opacity: 0.8;
  text-decoration: underline;
}

.resource-type {
  margin-left: var(--space-2);
}

/*: 步骤核验面板 */
.step-verify-section {
  margin-top: var(--space-6);
  text-align: left;
}

.verify-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
}

.verify-step-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
}

.verify-step-name {
  font-weight: 500;
  font-size: var(--font-size-sm);
}

.verify-error-hint {
  color: var(--destructive);
  font-size: var(--font-size-xs);
  margin-left: auto;
}

.verify-checks {
  padding: var(--space-2) 0;
}

.verify-check-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--border);
}

.verify-check-item:last-child {
  border-bottom: none;
}

.check-ok {
  color: var(--success);
  flex-shrink: 0;
  margin-top: 2px;
}

.check-fail {
  color: var(--destructive);
  flex-shrink: 0;
  margin-top: 2px;
}

.check-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.check-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--foreground);
}

.check-detail {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

.verify-samples {
  padding: var(--space-3) var(--space-4);
  border-top: 1px dashed var(--border);
}

.sample-block {
  margin-bottom: var(--space-3);
}

.sample-block:last-child {
  margin-bottom: 0;
}

.sample-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--muted-foreground);
  margin-bottom: var(--space-1);
}

.sample-value {
  background: var(--muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--foreground);
  max-height: 160px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', monospace);
}
</style>
