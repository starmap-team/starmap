<script setup lang="ts">
/**
 * ManualImportDialog — 手动导入 JD 弹窗
 * 支持 JSON 文件上传 + 文本粘贴 + 实时格式校验 + 导入结果展示
 */
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Document, WarningFilled, CircleCheckFilled } from '@element-plus/icons-vue'
import { getSourceNameLabel } from '@/composables/useDataSourceCharts'

const props = defineProps<{
  visible: boolean
  sourceId: string
  sourceName: string
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  imported: []
}>()

// --- 输入模式 ---
type InputMode = 'text' | 'file'
const inputMode = ref<InputMode>('text')
const textInput = ref('')
const fileList = ref<File[]>([])

// --- 校验 ---
interface JdItem {
  source_url: string
  raw_text: string
  title: string
  company?: string
  location?: string
  salary_min?: number
  salary_max?: number
}

const parsedJds = ref<JdItem[]>([])
const parseError = ref('')
const isValid = computed(() => parsedJds.value.length > 0 && !parseError.value)

// 实时校验（text 与 file 模式都读 textInput——文件内容已写入 textInput）
function validateInput() {
  parseError.value = ''
  parsedJds.value = []
  const raw = textInput.value || ''
  if (!raw.trim()) return
  let data: unknown
  try {
    data = JSON.parse(raw)
  } catch (e) {
    parseError.value = `JSON 解析失败: ${(e as Error).message}`
    return
  }
  if (!Array.isArray(data)) {
    parseError.value = '请输入 JSON 数组格式'
    return
  }
  if (data.length === 0) {
    parseError.value = '数组不能为空'
    return
  }
  const errors: string[] = []
  const valid: JdItem[] = []
  data.forEach((item, i) => {
    const obj = item as Record<string, unknown>
    if (!obj.source_url || !obj.raw_text) {
      errors.push(`第 ${i + 1} 条: 缺少 source_url 或 raw_text`)
      return
    }
    valid.push({
      source_url: String(obj.source_url),
      raw_text: String(obj.raw_text),
      title: String(obj.title || obj.job_title || '未命名'),
      company: obj.company ? String(obj.company) : undefined,
      location: obj.location ? String(obj.location) : undefined,
      salary_min: typeof obj.salary_min === 'number' ? obj.salary_min : undefined,
      salary_max: typeof obj.salary_max === 'number' ? obj.salary_max : undefined,
    })
  })
  if (errors.length > 0) {
    parseError.value = errors.slice(0, 5).join('; ') + (errors.length > 5 ? ` 等 ${errors.length} 条` : '')
  }
  parsedJds.value = valid
}

watch(textInput, validateInput)
watch(inputMode, () => {
  parseError.value = ''
  parsedJds.value = []
})

// --- 文件上传 ---
function handleFileChange(file: File) {
  inputMode.value = 'file'
  const reader = new FileReader()
  reader.onload = (e) => {
    textInput.value = (e.target?.result as string) || ''
    validateInput()
  }
  reader.readAsText(file)
  // 清除 el-upload 的 fileList 以避免重复触发
  fileList.value = []
}

function onFileChange(uploadFile: { raw?: File }) {
  if (uploadFile?.raw) handleFileChange(uploadFile.raw)
}

// --- 提交 ---
const submitting = ref(false)
const result = ref<{ inserted: number; duplicates: number; errors: string[] } | null>(null)

async function handleSubmit() {
  if (!isValid.value || submitting.value) return
  submitting.value = true
  result.value = null
  try {
    const { default: request } = await import('@/api/request')
    const out = await request.post(`/datasources/${props.sourceId}/manual-import`, {
      jds: parsedJds.value,
    }) as { inserted: number; duplicates: number; errors: string[] }
    result.value = out
    if (out.errors && out.errors.length > 0) {
      ElMessage.warning(`已导入 ${out.inserted} 条, ${out.duplicates} 条重复, 错误 ${out.errors.length} 条`)
    } else {
      ElMessage.success(`✅ 已导入 ${out.inserted} 条到「${getSourceNameLabel(props.sourceName)}」`)
    }
    if (out.inserted > 0) emit('imported')
  } catch (e) {
    ElMessage.error('手动导入失败: ' + ((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || (e as Error).message))
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  emit('update:visible', false)
  // 重置状态
  setTimeout(() => {
    textInput.value = ''
    parsedJds.value = []
    parseError.value = ''
    result.value = null
    inputMode.value = 'text'
  }, 200)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="手动导入 JD"
    width="640px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="import-dialog">
      <p class="import-hint">
        向「<strong>{{ getSourceNameLabel(sourceName) }}</strong>」手动导入 JD 数据。每条需包含
        <code>source_url</code> 和 <code>raw_text</code>。
      </p>

      <!-- 输入模式切换 -->
      <div class="mode-tabs">
        <el-radio-group
          v-model="inputMode"
          size="small"
        >
          <el-radio-button value="text">
            <el-icon class="el-icon--left">
              <Document />
            </el-icon>
            文本粘贴
          </el-radio-button>
          <el-radio-button value="file">
            <el-icon class="el-icon--left">
              <Upload />
            </el-icon>
            文件上传
          </el-radio-button>
        </el-radio-group>
      </div>

      <!-- 文本输入 -->
      <el-input
        v-if="inputMode === 'text'"
        v-model="textInput"
        type="textarea"
        :rows="8"
        placeholder="[{&quot;source_url&quot;:&quot;https://...&quot;,&quot;raw_text&quot;:&quot;...&quot;,&quot;title&quot;:&quot;前端工程师&quot;}]"
        spellcheck="false"
        class="import-textarea"
      />

      <!-- 文件上传 -->
      <el-upload
        v-if="inputMode === 'file'"
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".json,.jsonl,.txt"
        :before-upload="() => false"
        @change="onFileChange"
      >
        <el-icon
          class="el-icon--upload"
          size="40"
        >
          <Upload />
        </el-icon>
        <div class="el-upload__text">
          拖拽 JSON 文件到此处，或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 .json / .jsonl / .txt 文件
          </div>
        </template>
      </el-upload>

      <!-- 实时校验状态 -->
      <div
        v-if="parseError"
        class="validate-error"
      >
        <el-icon><WarningFilled /></el-icon>
        {{ parseError }}
      </div>
      <div
        v-else-if="parsedJds.length > 0"
        class="validate-ok"
      >
        <el-icon><CircleCheckFilled /></el-icon>
        已识别 {{ parsedJds.length }} 条有效 JD
      </div>

      <!-- 导入结果 -->
      <div
        v-if="result"
        class="import-result"
      >
        <el-result
          :icon="result.errors.length > 0 ? 'warning' : 'success'"
          :title="`导入完成: ${result.inserted} 条成功`"
          :sub-title="`${result.duplicates} 条重复${result.errors.length > 0 ? `, ${result.errors.length} 条错误` : ''}`"
        />
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">
        取消
      </el-button>
      <el-button
        type="primary"
        :disabled="!isValid || submitting"
        :loading="submitting"
        @click="handleSubmit"
      >
        {{ submitting ? '导入中...' : `导入 ${parsedJds.length} 条` }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.import-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.import-hint {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin: 0;
  line-height: 1.6;
}
.import-hint code {
  background: var(--muted);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: var(--font-size-xs);
}
.mode-tabs {
  display: flex;
  align-items: center;
}
.import-textarea :deep(textarea) {
  font-family: 'JetBrains Mono', monospace;
  font-size: var(--font-size-xs);
  line-height: 1.6;
}
.validate-error {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--destructive);
  padding: var(--space-2);
  background: color-mix(in srgb, var(--destructive) 8%, transparent);
  border-radius: var(--radius-md);
}
.validate-ok {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--success);
  padding: var(--space-2);
  background: color-mix(in srgb, var(--success) 8%, transparent);
  border-radius: var(--radius-md);
}
.import-result {
  margin-top: var(--space-2);
}
</style>
