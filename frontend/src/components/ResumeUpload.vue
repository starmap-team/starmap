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

// 模拟上传进度
async function startUpload() {
  if (!file.value) return
  uploading.value = true
  uploadProgress.value = 0

  // 模拟进度条
  const timer = setInterval(() => {
    if (uploadProgress.value >= 90) {
      clearInterval(timer)
    } else {
      uploadProgress.value += Math.random() * 20 + 5
      if (uploadProgress.value > 90) uploadProgress.value = 90
    }
  }, 200)

  // 实际调用（mock 或真实 API）
  try {
    emit('upload', file.value)
    uploadProgress.value = 100
    ElMessage.success('简历上传成功')
  } catch {
    ElMessage.error('上传失败，请重试')
  } finally {
    clearInterval(timer)
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
          style="margin-top: 12px"
        />
      </template>

      <!-- 已选文件 -->
      <template v-else-if="file">
        <div class="file-info">
          <span style="font-size: 36px">📄</span>
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
        <div style="font-size: 48px; color: #c0c4cc">
          📂
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
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  padding: 48px 24px;
  text-align: center;
  transition: border-color 0.3s, background 0.3s;
  cursor: pointer;
}

.upload-zone.is-dragover {
  border-color: #409eff;
  background: rgba(64, 158, 255, 0.05);
}

.upload-zone.has-file {
  border-style: solid;
  border-color: #67c23a;
}

.upload-text {
  font-size: 16px;
  color: #606266;
  margin-top: 12px;
}

.upload-hint {
  font-size: 13px;
  color: #c0c4cc;
  margin-top: 8px;
}

.upload-btn {
  display: inline-block;
  margin-top: 16px;
  padding: 8px 20px;
  background: #409eff;
  color: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.upload-btn:hover {
  background: #66b1ff;
}

.file-info {
  margin-bottom: 16px;
}

.file-name {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  margin-top: 8px;
}

.file-size {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.file-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}
</style>
