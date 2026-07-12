<script setup lang="ts">
/**
 * Prompt template management panel — version control + A/B testing.
 * Consumes usePromptStore which wraps all /admin/prompts/* endpoints.
 */
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePromptStore } from '@/stores/prompt'
import type { PromptVersionInfo } from '@/stores/prompt'

const prompt = usePromptStore()

const selectedPrompt = ref<string | null>(null)
const selectedVersion = ref<string | null>(null)
const abDialogVisible = ref(false)
const abCanary = ref('')
const abTraffic = ref(0.1)
const registerDialogVisible = ref(false)
const newTemplate = ref('')
const newVersionLabel = ref('')

onMounted(() => {
  prompt.fetchPrompts()
})

watch(selectedPrompt, (name) => {
  if (name) {
    selectedVersion.value = null
    prompt.fetchTemplate(name)
  }
})

watch(selectedVersion, (ver) => {
  if (selectedPrompt.value && ver) {
    prompt.fetchTemplate(selectedPrompt.value, ver)
  }
})

function handleSwitchVersion(name: string, version: string) {
  ElMessageBox.confirm(`确认将 ${name} 的活跃版本切换为 ${version}？`, '切换版本', {
    confirmButtonText: '确认',
    cancelButtonText: '取消',
  }).then(() => {
    prompt.switchActiveVersion(name, version).then(() => {
      ElMessage.success('版本已切换')
    }).catch(() => ElMessage.error('切换失败'))
  }).catch(() => { /* cancelled */ })
}

function handleStartAB() {
  if (!selectedPrompt.value || !abCanary.value) return
  prompt.startABTest(selectedPrompt.value, abCanary.value, abTraffic.value).then(() => {
    ElMessage.success('A/B测试已启动')
    abDialogVisible.value = false
    abCanary.value = ''
    abTraffic.value = 0.1
  }).catch(() => ElMessage.error('启动失败'))
}

function handleStopAB(name: string) {
  ElMessageBox.confirm(`确认停止 ${name} 的A/B测试？`, '停止测试', {
    confirmButtonText: '确认',
    cancelButtonText: '取消',
  }).then(() => {
    prompt.stopABTest(name).then(() => {
      ElMessage.success('A/B测试已停止')
    }).catch(() => ElMessage.error('停止失败'))
  }).catch(() => { /* cancelled */ })
}

function handleRegisterVersion() {
  if (!selectedPrompt.value || !newTemplate.value) return
  prompt.registerVersion(
    selectedPrompt.value,
    newTemplate.value,
    newVersionLabel.value || undefined,
  ).then(() => {
    ElMessage.success('新版本已注册')
    registerDialogVisible.value = false
    newTemplate.value = ''
    newVersionLabel.value = ''
  }).catch(() => ElMessage.error('注册失败'))
}

function handleViewABResults(name: string) {
  prompt.fetchABResults(name)
}

const promptNames = () => Object.keys(prompt.prompts)
const getInfo = (name: string): PromptVersionInfo | undefined => prompt.prompts[name]
</script>

<template>
  <div class="prompt-manager">
    <div class="prompt-layout">
      <!-- Left: prompt list -->
      <div class="prompt-list">
        <div
          v-for="name in promptNames()"
          :key="name"
          class="prompt-item"
          :class="{ active: selectedPrompt === name }"
          @click="selectedPrompt = name"
        >
          <span class="prompt-name">{{ name }}</span>
          <span
            v-if="getInfo(name)?.ab_test"
            class="ab-badge"
          >A/B</span>
        </div>
        <div
          v-if="!promptNames().length"
          class="empty-hint"
        >
          暂无Prompt模板
        </div>
      </div>

      <!-- Right: detail panel -->
      <div class="prompt-detail">
        <template v-if="selectedPrompt">
          <div class="detail-header">
            <h3>{{ selectedPrompt }}</h3>
            <div class="detail-actions">
              <el-button
                size="small"
                @click="registerDialogVisible = true"
              >
                注册新版本
              </el-button>
              <el-button
                v-if="!getInfo(selectedPrompt)?.ab_test"
                size="small"
                type="warning"
                @click="abDialogVisible = true"
              >
                启动A/B测试
              </el-button>
              <el-button
                v-else
                size="small"
                type="danger"
                @click="handleStopAB(selectedPrompt)"
              >
                停止A/B测试
              </el-button>
              <el-button
                size="small"
                @click="handleViewABResults(selectedPrompt)"
              >
                查看A/B结果
              </el-button>
            </div>
          </div>

          <!-- Version tags -->
          <div class="version-section">
            <span class="section-label">版本列表</span>
            <div class="version-tags">
              <el-tag
                v-for="ver in getInfo(selectedPrompt)?.versions ?? []"
                :key="ver"
                :type="ver === getInfo(selectedPrompt)?.active ? 'success' : 'info'"
                :effect="ver === selectedVersion ? 'dark' : 'plain'"
                class="version-tag"
                @click="selectedVersion = ver"
              >
                {{ ver }}
                <span v-if="ver === getInfo(selectedPrompt)?.active"> (活跃)</span>
              </el-tag>
            </div>
            <el-button
              v-if="selectedVersion && selectedVersion !== getInfo(selectedPrompt)?.active"
              size="small"
              type="primary"
              plain
              @click="handleSwitchVersion(selectedPrompt, selectedVersion)"
            >
              切换为此版本
            </el-button>
          </div>

          <!-- A/B test status -->
          <div
            v-if="getInfo(selectedPrompt)?.ab_test"
            class="ab-status"
          >
            <span class="section-label">A/B测试进行中</span>
            <div class="ab-info">
              <el-tag size="small">
                对照: {{ getInfo(selectedPrompt)?.ab_test?.control_version }}
              </el-tag>
              <el-tag
                size="small"
                type="warning"
              >
                实验版: {{ getInfo(selectedPrompt)?.ab_test?.canary_version }}
              </el-tag>
              <el-tag
                size="small"
                type="info"
              >
                流量: {{ ((getInfo(selectedPrompt)?.ab_test?.traffic_fraction ?? 0) * 100).toFixed(0) }}%
              </el-tag>
            </div>
          </div>

          <!-- A/B results -->
          <div
            v-if="Object.keys(prompt.abResults).length"
            class="ab-results"
          >
            <span class="section-label">A/B测试结果</span>
            <el-table
              :data="Object.entries(prompt.abResults).map(([v, s]) => ({ version: v, ...s }))"
              size="small"
              stripe
            >
              <el-table-column
                prop="version"
                label="版本"
                width="80"
              />
              <el-table-column
                prop="count"
                label="样本数"
                width="80"
                align="center"
              />
              <el-table-column
                prop="success_rate"
                label="成功率"
                width="90"
                align="center"
              >
                <template #default="{ row }">
                  {{ (row.success_rate * 100).toFixed(1) }}%
                </template>
              </el-table-column>
              <el-table-column
                prop="avg_f1"
                label="平均F1"
                width="90"
                align="center"
              >
                <template #default="{ row }">
                  {{ row.avg_f1 !== null ? row.avg_f1.toFixed(4) : '—' }}
                </template>
              </el-table-column>
              <el-table-column
                prop="avg_latency_ms"
                label="平均延迟(ms)"
                width="110"
                align="center"
              >
                <template #default="{ row }">
                  {{ row.avg_latency_ms !== null ? row.avg_latency_ms.toFixed(1) : '—' }}
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- Template content -->
          <div class="template-section">
            <span class="section-label">模板内容{{ selectedVersion ? ` (${selectedVersion})` : '' }}</span>
            <pre class="template-content">{{ prompt.currentTemplate || '选择Prompt查看模板内容' }}</pre>
          </div>
        </template>

        <div
          v-else
          class="empty-state"
        >
          请从左侧选择一个Prompt模板
        </div>
      </div>
    </div>

    <!-- A/B test dialog -->
    <el-dialog
      v-model="abDialogVisible"
      title="启动A/B测试"
      width="420px"
    >
      <el-form label-width="90px">
        <el-form-item label="实验版本">
          <el-input
            v-model="abCanary"
            placeholder="如 v3"
          />
        </el-form-item>
        <el-form-item label="流量比例">
          <el-slider
            v-model="abTraffic"
            :min="0.05"
            :max="0.5"
            :step="0.05"
            :format-tooltip="(v: number) => `${(v * 100).toFixed(0)}%`"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="abDialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="handleStartAB"
        >
          启动
        </el-button>
      </template>
    </el-dialog>

    <!-- Register version dialog -->
    <el-dialog
      v-model="registerDialogVisible"
      title="注册新版本"
      width="560px"
    >
      <el-form label-width="90px">
        <el-form-item label="版本标签">
          <el-input
            v-model="newVersionLabel"
            placeholder="留空自动递增"
          />
        </el-form-item>
        <el-form-item label="模板内容">
          <el-input
            v-model="newTemplate"
            type="textarea"
            :rows="8"
            placeholder="输入Prompt模板内容..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="registerDialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="handleRegisterVersion"
        >
          注册
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.prompt-manager {
  height: 100%;
}
.prompt-layout {
  display: flex;
  gap: 16px;
  height: 100%;
  min-height: 460px;
}
.prompt-list {
  width: 200px;
  flex-shrink: 0;
  border-right: 1px solid var(--el-border-color-lighter);
  padding-right: 12px;
}
.prompt-item {
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: background 0.15s;
}
.prompt-item:hover {
  background: var(--el-fill-color-light);
}
.prompt-item.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
}
.prompt-name {
  font-size: 13px;
}
.ab-badge {
  font-size: 11px;
  background: var(--el-color-warning-light-8);
  color: var(--el-color-warning);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}
.empty-hint {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
  padding: 16px 0;
  text-align: center;
}
.prompt-detail {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.detail-header h3 {
  margin: 0;
  font-size: 16px;
}
.detail-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.section-label {
  display: block;
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
.version-section {
  margin-bottom: 16px;
}
.version-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.version-tag {
  cursor: pointer;
}
.ab-status {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--el-color-warning-light-9);
  border-radius: 8px;
}
.ab-info {
  display: flex;
  gap: 6px;
}
.ab-results {
  margin-bottom: 16px;
}
.template-section {
  margin-top: 16px;
}
.template-content {
  background: var(--el-fill-color-lighter);
  padding: 12px;
  border-radius: 8px;
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 320px;
  overflow-y: auto;
  margin: 0;
}
.empty-state {
  color: var(--el-text-color-placeholder);
  text-align: center;
  padding: 60px 0;
}
</style>