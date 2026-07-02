<script setup lang="ts">
/**
 * 图谱节点编辑器
 * 支持创建/编辑 Skill / Position / Domain 节点
 * 提交后进入审核队列
 */
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Edit } from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
  editData?: {
    id?: string
    type: string
    name: string
    properties: Record<string, any>
  } | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'submit', data: any): void
  (e: 'close'): void
}>()

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
    form.type = props.editData.type || 'Skill'
    form.name = props.editData.name || ''
    form.category = props.editData.properties?.category || ''
    form.proficiency = props.editData.properties?.proficiency || ''
    form.level = props.editData.properties?.level || ''
    form.description = props.editData.properties?.description || ''
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
  <el-dialog
    v-model="dialogVisible"
    :title="isEditing ? '编辑图谱节点' : '新建图谱节点'"
    width="480px"
    :close-on-click-modal="false"
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
