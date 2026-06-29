<script setup lang="ts">
/**
 * 简历上传组件 — 拖拽 + 进度条 + 骨架屏 + 校验
 * 对应任务文档：匹配诊断第1步
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

const emit = defineEmits<{
  upload: [file: File]
}>()

// 接收父组件的异步上传函数
const asyncUploadFn = ref<((file: File) => Promise<void>) | null>(null)

defineExpose({
  setAsyncUploader(fn: (file: File) => Promise<void>) {
    asyncUploadFn.value = fn
  }
})

const file = ref<File | null>(null)
const uploading = ref(false)
const uploadProgress = ref(0)

const fileName = computed(() => file.value?.name ?? '')
const fileSize = computed(() => {
  if (!file.value) return ''
  const kb = file.value.size / 1024
  return kb > 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`
})

// 拖拽状态
const isDragover = ref(false)

function handleDragOver(e: DragEvent) {
  e.preventDefault()
  isDragover.value = true
}
function handleDragLeave() {
  isDragover.value = false
}
function handleDrop(e: DragEvent) {
  e.preventDefault()
  isDragover.value = false
  const droppedFile = e.dataTransfer?.files?.[0]
  if (droppedFile) validateAndSet(droppedFile)
}

// 文件选择
function handleFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const selected = target.files?.[0]
  if (selected) validateAndSet(selected)
}

// 校验文件
function validateAndSet(f: File) {
  const allowed = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']
  if (!allowed.includes(f.type)) {
    ElMessage.error('仅支持 PDF / Word 格式')
    return
  }
  if (f.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 10MB')
    return
  }
  file.value = f
}

// 上传进度
async function startUpload() {
  if (!file.value) return
  uploading.value = true
  uploadProgress.value = 50

  try {
    if (asyncUploadFn.value) {
      // 使用父组件提供的异步上传函数
      await asyncUploadFn.value(file.value)
    } else {
      // 回退到 emit 模式
      emit('upload', file.value)
    }
    uploadProgress.value = 100
    ElMessage.success('简历上传成功')
  } catch {
    ElMessage.error('上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

function handleRemove() {
  file.value = null
  uploadProgress.value = 0
}
</script>

<template>
  <div class="resume-upload">
    <!-- 拖拽区域 -->
    <div
      class="upload-zone"
      :class="{ 'is-dragover': isDragover, 'has-file': file }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <!-- 骨架屏（上传中） -->
      <template v-if="uploading">
        <el-skeleton
          :rows="3"
          animated
        />
        <el-progress
          :percentage="Math.round(uploadProgress)"
          :status="uploadProgress === 100 ? 'success' : undefined"
          class="progress-wrapper"
        />
      </template>

      <!-- 已选文件 -->
      <template v-else-if="file">
        <div class="file-info">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--primary)"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></svg>
          <div class="file-name">
            {{ fileName }}
          </div>
          <div class="file-size">
            {{ fileSize }}
          </div>
        </div>
        <div class="file-actions">
          <el-button
            type="primary"
            :loading="uploading"
            @click="startUpload"
          >
            开始上传解析
          </el-button>
          <el-button @click="handleRemove">
            移除
          </el-button>
        </div>
      </template>

      <!-- 空状态 -->
      <template v-else>
        <div class="upload-icon-wrapper">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/><path d="M12 10v6"/><path d="m9 13 3-3 3 3"/></svg>
        </div>
        <div class="upload-text">
          将简历文件拖到此处
        </div>
        <div class="upload-hint">
          支持 PDF、DOC、DOCX 格式，最大 10MB
        </div>
        <label class="upload-btn">
          选择文件
          <input
            type="file"
            accept=".pdf,.doc,.docx"
            hidden
            @change="handleFileChange"
          >
        </label>
      </template>
    </div>
  </div>
</template>

<style scoped>
.resume-upload {
  width: 100%;
}

.upload-zone {
  border: 2px dashed var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-12) var(--space-6);
  text-align: center;
  transition: border-color var(--duration-normal) var(--ease-in-out), background var(--duration-normal) var(--ease-in-out);
  cursor: pointer;
}

.upload-zone.is-dragover {
  border-color: var(--primary);
  background: var(--primary-ghost);
}

.upload-zone.has-file {
  border-style: solid;
  border-color: var(--success);
}

.upload-text {
  font-size: var(--font-size-lg);
  color: var(--foreground);
  margin-top: var(--space-3);
}

.upload-hint {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin-top: var(--space-2);
}

.upload-btn {
  display: inline-block;
  margin-top: var(--space-4);
  padding: var(--space-2) var(--space-5);
  background: var(--primary);
  color: var(--primary-foreground);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: background var(--duration-normal) var(--ease-in-out);
}

.upload-btn:hover {
  background: var(--primary-hover);
}

.file-info {
  margin-bottom: var(--space-4);
}

.file-name {
  font-size: var(--font-size-lg);
  font-weight: 500;
  color: var(--foreground);
  margin-top: var(--space-2);
}

.file-size {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin-top: var(--space-1);
}

.file-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
}

.progress-wrapper { margin-top: var(--space-3); }
.upload-icon-wrapper { color: var(--muted-foreground); }
</style>