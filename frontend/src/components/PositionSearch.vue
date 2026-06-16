<script setup lang="ts">
/**
 * 岗位搜索下拉组件 — 对应契约 GET /positions?search=
 */
import { ref, onMounted } from 'vue'

const emit = defineEmits<{
  select: [position: { position_id: string; name: string }]
}>()

const options = ref<{ label: string; value: string; position_id: string }[]>([])
const selected = ref('')
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const resp = await fetch('/api/v1/positions')
    const data = await resp.json()
    options.value = (data.items ?? []).map((p: { position_id: string; name: string }) => ({
      label: p.name,
      value: p.position_id,
      position_id: p.position_id,
    }))
  } finally {
    loading.value = false
  }
})

async function remoteMethod(q: string) {
  loading.value = true
  try {
    const resp = await fetch(`/api/v1/positions?search=${encodeURIComponent(q)}`)
    const data = await resp.json()
    options.value = (data.items ?? []).map((p: { position_id: string; name: string }) => ({
      label: p.name,
      value: p.position_id,
      position_id: p.position_id,
    }))
  } finally {
    loading.value = false
  }
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
  margin-top: 8px;
  font-size: 13px;
  color: #c0c4cc;
}
</style>
