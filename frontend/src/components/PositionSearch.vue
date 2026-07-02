<script setup lang="ts">
/**
 * 岗位搜索下拉组件 — 使用图谱岗位名称作为 canonical 源
 */
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

const emit = defineEmits<{
  select: [position: { position_id: string; name: string }]
}>()

const options = ref<{ label: string; value: string; position_id: string }[]>([])
const selected = ref('')
const loading = ref(false)

async function loadPositions(keyword?: string) {
  loading.value = true
  try {
    const params: Record<string, string | number> = { page_size: 100 }
    if (keyword?.trim()) {
      params.search = keyword.trim()
    }
    const data = await request.get('/positions', { params }) as any
    options.value = (data.items ?? []).map((p: { position_id: string; name: string }) => ({
      label: p.name,
      value: p.name,
      position_id: p.position_id,
    }))
  } catch (e) {
    console.error('[PositionSearch] Failed to load positions:', e)
    ElMessage.error('岗位列表加载失败')
    options.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => loadPositions())

async function remoteMethod(q: string) {
  await loadPositions(q)
}

function handleChange(val: string) {
  if (val) {
    const opt = options.value.find(o => o.value === val)
    if (opt) emit('select', { position_id: opt.position_id, name: opt.label })
  }
}
</script>

<template>
  <div class="position-search">
    <el-select
      v-model="selected"
      filterable
      remote
      reserve-keyword
      placeholder="请搜索并选择目标岗位"
      :remote-method="remoteMethod"
      :loading="loading"
      size="large"
      style="width: 100%"
      @change="handleChange"
    >
      <el-option
        v-for="opt in options"
        :key="opt.value"
        :label="opt.label"
        :value="opt.value"
      />
    </el-select>
    <div class="hint">
      输入岗位名称关键词搜索，如"数据分析"、"前端"等
    </div>
  </div>
</template>

<style scoped>
.position-search {
  width: 100%;
}

.hint {
  margin-top: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
}
</style>