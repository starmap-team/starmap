<!--
  PipelineMonitor 定时调度表单子组件（ Plan 03 Task 8/11 实际迁移）。
  T8：Cron 5 字段完整校验（值域 + 范围）+ 错误提示 + 常用示例 tooltip。
-->
<script setup lang="ts">
import { computed } from 'vue'
import { RUN_TYPE_LABELS } from '@/constants/labels'
import { validateCron, CRON_EXAMPLES } from '@/utils/cronValidator'

export interface ScheduleFormModel {
  name: string
  cron_expression: string
  run_type: 'full' | 'incremental'
  selected_stages: string[] | null
  selected_sources: string[] | null
  enabled: boolean
}

export interface ScheduleSourceOption {
  name: string
  label: string
  icon?: string
}

const props = defineProps<{
  modelValue: boolean
  form: ScheduleFormModel
  availableSources?: ScheduleSourceOption[]
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'update:form', value: ScheduleFormModel): void
  (e: 'submit'): void
}>()

const cronResult = computed(() => validateCron(props.form.cron_expression))
const cronErrors = computed(() => cronResult.value.errors)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="创建定时调度"
    width="480px"
    align-center
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form
      :model="form"
      label-width="100px"
    >
      <el-form-item label="名称">
        <el-input
          :model-value="form.name"
          placeholder="如：每日增量爬取"
          @update:model-value="emit('update:form', { ...form, name: $event as string })"
        />
      </el-form-item>
      <el-form-item label="Cron 表达式">
        <el-tooltip
          placement="top"
          effect="dark"
        >
          <template #content>
            <div style="line-height: 1.6">
              格式: 分 时 日 月 周<br>
              示例:<br>
              <code
                v-for="ex in CRON_EXAMPLES"
                :key="ex.expression"
              >
                {{ ex.expression }} = {{ ex.description }}<br>
              </code>
            </div>
          </template>
          <el-input
            :model-value="form.cron_expression"
            :class="{ 'is-error': !cronResult.valid }"
            placeholder="分 时 日 月 周，如 0 2 * * *"
            @update:model-value="emit('update:form', { ...form, cron_expression: $event as string })"
          />
        </el-tooltip>
        <div
          v-for="err in cronErrors"
          :key="err.field"
          class="cron-hint-error"
        >
          {{ err.message }}
        </div>
        <div
          v-if="cronResult.valid && form.cron_expression.trim()"
          class="cron-hint-ok"
        >
          Cron 表达式合法 ✓
        </div>
      </el-form-item>
      <el-form-item label="运行类型">
        <el-radio-group
          :model-value="form.run_type"
          @update:model-value="emit('update:form', { ...form, run_type: $event as 'full' | 'incremental' })"
        >
          <el-radio value="full">
            {{ RUN_TYPE_LABELS.full }}
          </el-radio>
          <el-radio value="incremental">
            {{ RUN_TYPE_LABELS.incremental }}
          </el-radio>
        </el-radio-group>
      </el-form-item>
      <!-- D8: 定时调度自选源（空 = 全部源） -->
      <el-form-item label="数据源">
        <el-tooltip
          content="选择定时触发时要爬取的源；不选 = 全部启用的爬虫源。"
          placement="top"
          effect="dark"
        >
          <el-checkbox-group
            :model-value="form.selected_sources ?? []"
            @update:model-value="emit('update:form', { ...form, selected_sources: ($event as string[]).length ? ($event as string[]) : null })"
          >
            <el-checkbox
              v-for="src in availableSources ?? []"
              :key="src.name"
              :value="src.name"
            >
              {{ src.icon ? src.icon + ' ' : '' }}{{ src.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-tooltip>
        <div
          v-if="!form.selected_sources?.length"
          class="cron-hint-ok"
        >
          未选择 = 爬取全部启用源
        </div>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch
          :model-value="form.enabled"
          @update:model-value="emit('update:form', { ...form, enabled: $event as boolean })"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">
        取消
      </el-button>
      <el-button
        type="primary"
        :disabled="!cronResult.valid || !form.name.trim()"
        :loading="loading"
        @click="emit('submit')"
      >
        创建
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.cron-hint-error {
  color: var(--el-color-danger);
  font-size: var(--font-size-xs);
  margin-top: 4px;
}
.cron-hint-ok {
  color: var(--el-color-success);
  font-size: var(--font-size-xs);
  margin-top: 4px;
}
:deep(.el-input.is-error .el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--el-color-danger) inset;
}
</style>
