<script setup lang="ts">
/**
 * 图谱节点编辑器
 * 支持创建/编辑 Skill / Position / Domain 节点
 * 提交后进入审核队列
 */
import { reactive, ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  visible: boolean
  editData?: {
    id?: string
    type: string
    name: string
    properties: Record<string, unknown>
  } | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'update:modelValue', val: boolean): void
  (e: 'submit', data: { id?: string; type: string; name: string; properties: Record<string, unknown> }): void
  (e: 'close'): void
}>()

// E5 final: use computed wrapper. el-dialog v-model:visible works
// reliably across all viewports with align-center: true.
const dialogVisible = computed({
  get: () => props.visible,
  set: (val: boolean) => emit('update:visible', val),
})

const isEditing = computed(() => !!props.editData?.id)

const form = reactive({
  type: 'Skill' as string,
  name: '',
  category: '',
  proficiency: '',
  level: '',
  description: '',
})

const nodeTypes = [
  { value: 'Skill', label: '技能' },
  { value: 'Position', label: '岗位' },
  { value: 'Domain', label: '领域' },
]

const categories = [
  { value: 'hard_skill', label: '硬技能' },
  { value: 'soft_skill', label: '软技能' },
  { value: 'tool', label: '工具' },
  { value: 'certificate', label: '证书' },
]

const proficiencyOptions = [
  { value: '了解', label: '了解' },
  { value: '熟悉', label: '熟悉' },
  { value: '精通', label: '精通' },
]

// Reset form when dialog opens/closes or editData changes
watch(() => props.visible, (val) => {
  if (val && props.editData) {
    const p = props.editData.properties as Record<string, string | undefined>
    form.type = props.editData.type || 'Skill'
    form.name = props.editData.name || ''
    form.category = p?.category || ''
    form.proficiency = p?.proficiency || ''
    form.level = p?.level || ''
    form.description = p?.description || ''
  } else if (val) {
    resetForm()
  }
})

function resetForm() {
  form.type = 'Skill'
  form.name = ''
  form.category = ''
  form.proficiency = ''
  form.level = ''
  form.description = ''
}

function handleSubmit() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入节点名称')
    return
  }

  const nodeData = {
    id: props.editData?.id,
    type: form.type,
    name: form.name.trim(),
    properties: {
      category: form.category || undefined,
      proficiency: form.proficiency || undefined,
      level: form.level || undefined,
      description: form.description || undefined,
    },
  }

  emit('submit', nodeData)
  dialogVisible.value = false
  resetForm()
}

function handleClose() {
  dialogVisible.value = false
  emit('close')
}
</script>

<template>
  <!--
    E5 retry: original el-dialog was clipped on small viewports when the
    trigger button was near the bottom. Tried el-drawer but Element Plus
    2.14's drawer rtl transform animation stalls on first open. Fall
    back to el-dialog with align-center: true (which Element Plus
    2.14 does support reliably) plus a wrapper that locks the dialog to
    the viewport center. Additionally, when the dialog height exceeds
    viewport - 8vh, it switches to overflow-y: auto so the body becomes
    scrollable and the user can always reach the footer.
  -->
  <el-dialog
    v-model="dialogVisible"
    :title="isEditing ? `编辑图谱节点 — ${form.name || ''}` : '新建图谱节点'"
    width="480px"
    :close-on-click-modal="false"
    :align-center="false"
    :top="'4vh'"
    append-to-body
    modal-class="node-editor-dialog"
    @close="handleClose"
  >
    <el-form
      label-width="90px"
      class="node-form"
    >
      <el-form-item
        label="节点类型"
        required
      >
        <el-select
          v-model="form.type"
          style="width: 100%"
          :disabled="isEditing"
        >
          <el-option
            v-for="t in nodeTypes"
            :key="t.value"
            :label="t.label"
            :value="t.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item
        label="名称"
        required
      >
        <el-input
          v-model="form.name"
          :placeholder="form.type === 'Skill' ? '如：Python' : form.type === 'Position' ? '如：前端工程师' : '如：人工智能'"
          maxlength="100"
          show-word-limit
        />
      </el-form-item>

      <!-- 技能特有字段 -->
      <template v-if="form.type === 'Skill'">
        <el-form-item label="技能类别">
          <el-select
            v-model="form.category"
            placeholder="选择类别"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="c in categories"
              :key="c.value"
              :label="c.label"
              :value="c.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="熟练程度">
          <el-select
            v-model="form.proficiency"
            placeholder="选择程度"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="p in proficiencyOptions"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
        </el-form-item>
      </template>

      <!-- 岗位特有字段 -->
      <template v-if="form.type === 'Position'">
        <el-form-item label="级别">
          <el-select
            v-model="form.level"
            placeholder="选择级别"
            clearable
            style="width: 100%"
          >
            <el-option
              label="初级"
              value="junior"
            />
            <el-option
              label="中级"
              value="mid"
            />
            <el-option
              label="高级"
              value="senior"
            />
            <el-option
              label="专家"
              value="expert"
            />
          </el-select>
        </el-form-item>
      </template>

      <el-form-item label="描述">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          placeholder="节点描述（可选）"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="handleSubmit"
        >
          {{ isEditing ? '保存修改' : '提交审核' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.node-form {
  padding: var(--space-2) 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>

<!--
  E5 final + E23 retry: align-center removed, top=4vh, max-height=80vh.
  Rationale: with align-center the dialog is positioned at viewport center
  via flexbox align-items. When the trigger button is at the bottom of
  a long table, the user perceives the dialog as "appearing somewhere
  off-screen" because the relative offset is huge. By using
  align-center=false + top=4vh, the dialog now appears at a fixed
  position (4vh from top) regardless of the button location. This trades
  a little bit of visual centering for predictability.
-->
<style>
/* Default: align-center=false + top:4vh + max-height:80vh (set on el-dialog
   inline) keeps the dialog at a fixed offset, predictable regardless of
   trigger button position. */
.node-editor-dialog .el-dialog__body {
  max-height: calc(80vh - 140px);
  overflow-y: auto;
}
.node-editor-dialog .el-dialog {
  max-height: 80vh;
  margin-top: 0 !important;
  margin-bottom: 0 !important;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* E23 fix: on viewports shorter than 700px (small laptops / browser
   panels with bookmarks/taskbar), the dialog + footer cannot fit at
   80vh. Make the dialog a fixed-position bottom sheet pinned to the
   viewport bottom. Use `inset` shorthand to avoid the Element Plus
   internal transform/translate3d conflict. Body fills the remaining
   vertical space (flex: 1), and the footer is pinned at the bottom. */
@media (max-height: 700px) {
  .node-editor-dialog .el-dialog {
    position: fixed !important;
    inset: auto auto 0 0 !important;  /* top right bottom left — bottom:0 */
    margin: 0 !important;
    width: 100vw !important;
    max-width: 480px;
    height: auto !important;
    max-height: calc(100vh - 8px);
    border-radius: 12px 12px 0 0;
  }
  .node-editor-dialog .el-dialog__body {
    max-height: calc(100vh - 140px);
    flex: 1 1 auto;
  }
}
.node-editor-dialog .el-dialog__footer {
  /* footer 始终钉在 dialog 底部 */
  flex-shrink: 0;
  border-top: 1px solid var(--el-border-color-lighter);
  padding: 12px 16px;
  background: var(--el-bg-color);
}
</style>
