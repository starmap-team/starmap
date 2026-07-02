<template>
  <div class="pipeline-analysis">
    <h2>求职者分析</h2>
    <p class="subtitle">上传简历，获得完整的技能评估、岗位匹配和学习路径推荐</p>

    <!-- Step 1: 上传区域 -->
    <el-card v-if="!store.loading && !store.result" class="upload-card">
      <el-upload
        drag
        :auto-upload="false"
        :on-change="handleFileChange"
        :limit="1"
        accept=".pdf,.docx,.doc"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽简历到此处，或 <em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 PDF / DOCX 格式</div>
        </template>
      </el-upload>

      <div class="actions">
        <el-button type="primary" :disabled="!selectedFile" @click="startAnalysis">
          开始分析
        </el-button>
      </div>
    </el-card>

    <!-- Step 2: 进度 -->
    <el-card v-if="store.loading" class="progress-card">
      <h3>分析中...</h3>
      <el-steps :active="activeStep" finish-status="success" align-center>
        <el-step title="简历解析" />
        <el-step title="技能提取" />
        <el-step title="岗位匹配" />
        <el-step title="学习路径" />
        <el-step title="岗位推荐" />
      </el-steps>
      <div class="progress-log">
        <div v-for="(p, i) in store.progress" :key="i" class="log-item">
          <el-tag :type="statusType(p.status)" size="small">{{ p.step }}</el-tag>
          <span>{{ statusText(p.status) }}</span>
        </div>
      </div>
    </el-card>

    <!-- Step 3: 结果 -->
    <el-card v-if="store.result" class="result-card">
      <template #header>
        <div class="result-header">
          <span>分析结果</span>
          <div>
            <el-button text type="primary" @click="viewInGraph">查看图谱</el-button>
            <el-button text type="primary" @click="exportJSON">导出 JSON</el-button>
            <el-button text @click="store.reset()">重新分析</el-button>
          </div>
        </div>
      </template>

      <!-- 4个核心问题卡片 -->
      <el-row :gutter="16" class="kpi-row">
        <el-col :span="6">
          <el-statistic title="提取技能" :value="store.result.extracted_skills.length" suffix="项" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="匹配岗位" :value="store.result.top_matches.length" suffix="个" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="推荐岗位" :value="store.result.recommended_positions.length" suffix="个" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="技能差距" :value="store.result.skill_gaps.filter(g => g.gap_level !== '已掌握').length" suffix="项" />
        </el-col>
      </el-row>

      <!-- 问题1: 适合什么岗位 -->
      <h3>🎯 我适合什么岗位？</h3>
      <el-table :data="store.result.top_matches.slice(0, 5)" stripe size="small">
        <el-table-column prop="position" label="岗位" />
        <el-table-column prop="match_score" label="匹配度" width="100">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.match_score * 100)" :stroke-width="12" />
          </template>
        </el-table-column>
        <el-table-column prop="assessment" label="评估" />
        <el-table-column prop="gap_count" label="差距数" width="80" />
      </el-table>

      <!-- 问题2: 缺什么技能 -->
      <h3>📋 我缺什么技能？</h3>
      <el-table :data="store.result.skill_gaps.filter(g => g.gap_level !== '已掌握').slice(0, 10)" stripe size="small">
        <el-table-column prop="skill" label="技能" />
        <el-table-column prop="importance" label="重要性" width="100" />
        <el-table-column prop="gap_level" label="差距程度" width="100">
          <template #default="{ row }">
            <el-tag :type="row.gap_level === '完全缺失' ? 'danger' : 'warning'" size="small">
              {{ row.gap_level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="掌握度" width="100">
          <template #default="{ row }">
            {{ Math.round(row.score * 100) }}%
          </template>
        </el-table-column>
      </el-table>

      <!-- 问题3: 该学什么 -->
      <h3>📚 我该学什么？</h3>
      <div v-if="store.result.learning_path_summary.length">
        <div v-for="(path, i) in store.result.learning_path_summary.slice(0, 3)" :key="i" class="learning-path">
          <el-tag v-for="(step, j) in path" :key="j" :type="j === 0 ? 'danger' : j === path.length - 1 ? 'success' : ''" class="path-step">
            {{ step }}
          </el-tag>
        </div>
      </div>
      <el-empty v-else description="暂无学习路径数据" />

      <!-- 学习资源推荐 -->
      <h3 v-if="gapsWithResources.length">📖 推荐学习资源</h3>
      <div v-for="gap in gapsWithResources" :key="gap.skill" class="resource-section">
        <h4>{{ gap.skill }} <el-tag type="danger" size="small">{{ gap.gap_level }}</el-tag></h4>
        <ul class="resource-list">
          <li v-for="(res, ri) in gap.learning_resources" :key="ri">
            <a v-if="res.url" :href="res.url" target="_blank">{{ res.name }}</a>
            <span v-else>{{ res.name }}</span>
            <el-tag v-if="res.type" size="small" type="info" class="resource-type">{{ res.type }}</el-tag>
          </li>
        </ul>
      </div>

      <!-- 问题4: 推荐岗位 -->
      <h3>🚀 推荐岗位</h3>
      <el-table :data="store.result.recommended_positions.slice(0, 5)" stripe size="small">
        <el-table-column prop="position" label="岗位" />
        <el-table-column prop="score" label="综合得分" width="100">
          <template #default="{ row }">
            {{ (row.score * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column prop="match_score" label="匹配度" width="100">
          <template #default="{ row }">
            {{ (row.match_score * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column prop="developability" label="可发展性" width="100">
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
          <li v-for="(e, i) in store.result.errors" :key="i">{{ e }}</li>
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
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { UploadFilled } from '@element-plus/icons-vue'
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
}

const activeStep = computed(() => {
  if (!store.currentStep) return 0
  return (stepMap[store.currentStep] ?? 0) + 1
})

function handleFileChange(file: any) {
  selectedFile.value = file.raw
}

function startAnalysis() {
  if (selectedFile.value) {
    store.analyzeResume(selectedFile.value)
  }
}

function viewInGraph() {
  if (!store.result?.top_matches?.length) return
  const topPosition = store.result.top_matches[0].position
  router.push({ path: '/', query: { highlight: topPosition } })
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
</script>

<style scoped>
.pipeline-analysis {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}

.subtitle {
  color: var(--el-text-color-secondary);
  margin-bottom: 24px;
}

.upload-card {
  text-align: center;
}

.actions {
  margin-top: 16px;
}

.progress-card {
  text-align: center;
}

.progress-log {
  margin-top: 24px;
  text-align: left;
}

.log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.kpi-row {
  margin-bottom: 24px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

h3 {
  margin: 24px 0 12px;
  color: var(--el-text-color-primary);
}

.learning-path {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  flex-wrap: wrap;
}

.path-step {
  font-size: 13px;
}

.resource-section {
  margin: 8px 0 16px;
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.resource-section h4 {
  margin: 0 0 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.resource-list {
  margin: 0;
  padding-left: 20px;
}

.resource-list li {
  padding: 4px 0;
}

.resource-list a {
  color: var(--el-color-primary);
  text-decoration: none;
}

.resource-list a:hover {
  text-decoration: underline;
}

.resource-type {
  margin-left: 8px;
}
</style>
