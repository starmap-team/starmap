<script setup lang="ts">
import { ref } from "vue"
import { Connection } from "@element-plus/icons-vue"
import { useGraphStore } from "@/stores/graph"

const graphStore = useGraphStore()

const visible = ref(false)
const selectedEdge = ref<typeof graphStore.evolutionPaths[number] | null>(null)

const trendLabel: Record<string, string> = { rising: '↑ 上升', stable: '→ 平稳', declining: '↓ 下降' }
const trendType: Record<string, string> = { rising: 'success', stable: 'info', declining: 'danger' }

function open(edge: { source: string | { id: string }; target: string | { id: string } }) {
  const sId = typeof edge.source === 'string' ? edge.source : edge.source?.id ?? ''
  const tId = typeof edge.target === 'string' ? edge.target : edge.target?.id ?? ''
  const match = graphStore.evolutionPaths.find(e => e.source_id === sId && e.target_id === tId)
    ?? graphStore.evolutionPaths.find(e => (e.source_id === sId && e.target_id === tId) || (e.source_id === tId && e.target_id === sId))
  selectedEdge.value = match ?? null
  visible.value = true
}

function close() {
  visible.value = false
  selectedEdge.value = null
}

defineExpose({ open, close })
</script>

<template>
  <el-drawer
    v-model="visible"
    title="演化路径详情"
    size="420px"
    direction="rtl"
    @close="close"
  >
    <div v-if="selectedEdge" class="evo-drawer-body">
      <div class="evo-title-row">
        <span class="evo-pos">{{ selectedEdge.source_id }}</span>
        <el-icon :size="20" color="var(--primary)"><Connection /></el-icon>
        <span class="evo-pos">{{ selectedEdge.target_id }}</span>
      </div>
      <el-tag
        :type="(trendType[selectedEdge.properties?.trend ?? 'stable'] ?? 'info') as any"
        effect="plain"
        size="default"
      >{{ trendLabel[selectedEdge.properties?.trend ?? 'stable'] ?? selectedEdge.properties?.trend }}</el-tag>
      <el-descriptions :column="1" border class="evo-desc">
        <el-descriptions-item label="相似度">{{ ((selectedEdge.properties?.similarity ?? 0) * 100).toFixed(0) }}%</el-descriptions-item>
        <el-descriptions-item label="证据数">{{ selectedEdge.properties?.evidence_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="信任度">{{ ((selectedEdge.properties?.similarity ?? 0) * 100).toFixed(0) }}%</el-descriptions-item>
      </el-descriptions>
      <div v-if="selectedEdge.properties?.skill_overlap?.length" class="evo-section">
        <div class="evo-section-title">技能重叠 ({{ selectedEdge.properties.skill_overlap.length }})</div>
        <div class="evo-tags">
          <el-tag v-for="s in selectedEdge.properties.skill_overlap" :key="s" size="small" effect="plain" type="success">{{ s }}</el-tag>
        </div>
      </div>
      <div v-if="selectedEdge.properties?.key_gaps?.length" class="evo-section">
        <div class="evo-section-title">关键差距 ({{ selectedEdge.properties.key_gaps.length }})</div>
        <div class="evo-tags">
          <el-tag v-for="g in selectedEdge.properties.key_gaps" :key="g" size="small" effect="plain" type="danger">{{ g }}</el-tag>
        </div>
      </div>
    </div>
    <div v-else class="evo-empty">未选中演化边</div>
  </el-drawer>
</template>

<style scoped>
.evo-drawer-body { display: flex; flex-direction: column; gap: var(--space-4); padding: var(--space-2) 0; }
.evo-title-row { display: flex; align-items: center; justify-content: center; gap: var(--space-3); font-size: var(--font-size-lg); font-weight: 700; color: var(--foreground); }
.evo-pos { padding: 6px 14px; background: var(--card); border: 1px solid var(--border); border-radius: var(--radius-md); letter-spacing: var(--tracking-tight); }
.evo-desc { margin-top: var(--space-2); }
.evo-section { display: flex; flex-direction: column; gap: var(--space-2); }
.evo-section-title { font-size: var(--font-size-sm); font-weight: 600; color: var(--muted-foreground); text-transform: uppercase; letter-spacing: 0.06em; }
.evo-tags { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.evo-empty { padding: var(--space-10); text-align: center; color: var(--muted-foreground); font-size: var(--font-size-sm); }
</style>
