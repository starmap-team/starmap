<script setup lang="ts">
/**
 * 岗位列表页 — 从 MOCK_GRAPH 取 Position 节点
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const router = useRouter()
const positions = ref<{ id: string; name: string; industry: string }[]>([])
const loading = ref(false)

async function fetchPositions() {
  loading.value = true
  const resp = await fetch('/api/v1/graph/query')
  const data = await resp.json()
  positions.value = data.nodes
    .filter((n: any) => n.labels.includes('Position'))
    .map((n: any) => ({
      id: n.id,
      name: n.properties.name,
      industry: '互联网/IT',
    }))
  loading.value = false
}

function goDetail(name: string) {
  router.push(`/position/${encodeURIComponent(name)}`)
}

onMounted(fetchPositions)
</script>

<template>
  <MainLayout>
    <div class="position-list-page">
      <div class="page-header">
        <h2>岗位列表</h2>
        <p class="subtitle">选择岗位查看能力雷达图与技能详情</p>
      </div>

      <el-row :gutter="20" v-loading="loading">
        <el-col v-for="pos in positions" :key="pos.id" :xs="24" :sm="12" :md="8" :lg="6">
          <el-card class="position-card" shadow="hover" @click="goDetail(pos.name)">
            <div class="card-content">
            
              <h3>{{ pos.name }}</h3>
              <el-tag size="small" type="info">{{ pos.industry }}</el-tag>
            </div>
            <template #footer>
              <el-button type="primary" size="small" link> 查看详情 → </el-button>
            </template>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </MainLayout>
</template>

<style scoped>
.position-list-page {
  min-height: 400px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0 0 4px;
  font-size: 22px;
  color: #303133;
}

.subtitle {
  margin: 0;
  font-size: 14px;
  color: #909399;
}

.position-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  margin-bottom: 20px;
}

.position-card:hover {
  transform: translateY(-4px);
}

.card-content {
  text-align: center;
  padding: 12px 0;
}

.card-icon {
  font-size: 36px;
  margin-bottom: 8px;
}

.card-content h3 {
  margin: 0 0 8px;
  font-size: 16px;
  color: #303133;
}
</style>
