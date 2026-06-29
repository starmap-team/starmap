<script setup lang="ts">
/**
 * 岗位详情页 — 能力雷达图 + 技能列表
 * 路由：/position/:name
 */
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import SkillRadar, { type RadarItem } from '@/components/SkillRadar.vue'
import request from '@/api/request'

const route = useRoute()
const positionName = computed(() => route.params.name as string)

// ── 数据 ──
interface SkillItem {
  skill_id: string
  name: string
  category: string
  proficiency: string
  confidence: number
  source_count: number
}

interface PositionInfo {
  name: string
  industry: string
  description: string
}

const position = ref<PositionInfo | null>(null)
const skills = ref<SkillItem[]>([])
const loading = ref(false)

// ── 熟练度 → 0-1 映射 ──
const PROFICIENCY_MAP: Record<string, number> = {
  '精通': 1.0,
  '熟悉': 0.66,
  '了解': 0.33,
}

// ── 雷达图数据 ──
const radarData = computed<RadarItem[]>(() =>
  skills.value.map(s => ({
    skill: s.name,
    required: PROFICIENCY_MAP[s.proficiency] ?? 0.5,
    user: 0, // 岗位详情仅展示要求，无用户对比
  }))
)

const CATEGORY_LABELS: Record<string, string> = {
  hard_skill: '硬技能',
  soft_skill: '软技能',
  tool: '工具',
}

const PROFICIENCY_TAG: Record<string, string> = {
  '精通': 'danger',
  '熟悉': 'warning',
  '了解': 'info',
}

// ── 加载 ──
onMounted(async () => {
  loading.value = true
  try {
    const data = await request.get(`/graph/position/${encodeURIComponent(positionName.value)}/skills`)
    position.value = (data as any).position as PositionInfo
    skills.value = ((data as any).skills ?? []) as SkillItem[]
  } catch (e) {
    console.error('[PositionDetail] Failed to load:', e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <MainLayout>
    <div
      v-loading="loading"
      class="position-detail"
    >
      <!-- 返回 + 标题 -->
      <div class="page-header">
        <el-button
          circle
          :icon="ArrowLeft"
          size="small"
          @click="$router.push('/positions')"
        />
        <div>
          <h2>{{ position?.name ?? positionName }}</h2>
          <p class="header-sub">
            {{ position?.industry ?? '' }}
          </p>
        </div>
      </div>

      <div class="detail-body">
        <!-- 左侧：雷达图 -->
        <section class="radar-section">
          <SkillRadar
            :data="radarData"
            :position-name="positionName"
          />
        </section>

        <!-- 右侧：技能列表 -->
        <section class="skills-section">
          <h3 class="section-title">
            技能要求 ({{ skills.length }})
          </h3>
          <el-table
            :data="skills"
            stripe
            size="small"
            style="width: 100%"
          >
            <el-table-column
              prop="name"
              label="技能"
              min-width="120"
            />
            <el-table-column
              label="类别"
              width="100"
            >
              <template #default="{ row }">
                <el-tag size="small">
                  {{ CATEGORY_LABELS[row.category] ?? row.category }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="熟练度"
              width="80"
            >
              <template #default="{ row }">
                <el-tag
                  :type="PROFICIENCY_TAG[row.proficiency] ?? ''"
                  size="small"
                >
                  {{ row.proficiency }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="置信度"
              width="90"
            >
              <template #default="{ row }">
                {{ (row.confidence * 100).toFixed(0) }}%
              </template>
            </el-table-column>
            <el-table-column
              label="热度"
              width="60"
            >
              <template #default="{ row }">
                {{ row.source_count }}
              </template>
            </el-table-column>
          </el-table>
        </section>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.position-detail {
  max-width: 1100px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.header-sub {
  color: #909399;
  font-size: 13px;
  margin: 2px 0 0;
}

.detail-body {
  display: flex;
  gap: 24px;
}

.radar-section {
  flex: 0 0 420px;
}

.skills-section {
  flex: 1;
  min-width: 0;
}

.section-title {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
  margin: 0 0 12px;
}
</style>
