<script setup lang="ts">
/**
 * 岗位详情页 — 能力雷达图 + 技能列表
 * 路由：/position/:name
 */
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
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

// ── 加载（Neo4j 优先，PostgreSQL 回退） ──
onMounted(async () => {
  loading.value = true
  try {
    const data = await request.get(`/graph/position/${encodeURIComponent(positionName.value)}/skills`)
    if ((data as any)?.skills?.length || (data as any)?.position) {
      position.value = (data as any).position as PositionInfo
      skills.value = ((data as any).skills ?? []) as SkillItem[]
    } else {
      // Neo4j 无数据，回退到 PostgreSQL
      await loadFromPostgres()
    }
  } catch (e) {
    // Neo4j 查询失败（如 404），回退到 PostgreSQL
    console.warn('[PositionDetail] Neo4j lookup failed, trying PostgreSQL:', e)
    await loadFromPostgres()
  } finally {
    loading.value = false
  }
})

async function loadFromPostgres() {
  try {
    const pgData = await request.get(`/positions/${encodeURIComponent(positionName.value)}`)
    position.value = {
      name: (pgData as any).name ?? positionName.value,
      industry: (pgData as any).industry ?? '',
      description: (pgData as any).description ?? '',
    }
    skills.value = ((pgData as any).skills_required ?? []).map((s: any) => ({
      skill_id: s.skill_id ?? '',
      name: s.name ?? '',
      category: s.category ?? 'hard_skill',
      proficiency: s.proficiency ?? '熟悉',
      confidence: s.confidence ?? 1.0,
      source_count: s.source_count ?? 0,
    }))
  } catch (pgErr) {
    console.error('[PositionDetail] PostgreSQL fallback also failed:', pgErr)
    ElMessage.error('岗位详情加载失败，请确认该岗位存在')
  }
}
</script>

	<template>
	  <MainLayout>
	    <div class="position-detail">
	      <!-- 骨架屏加载态 -->
	      <template v-if="loading">
	        <div class="page-header">
	          <el-skeleton :rows="0" animated style="width: 200px">
	            <template #template>
	              <el-skeleton-item variant="circle" style="width: 32px; height: 32px" />
	              <el-skeleton-item variant="text" style="width: 150px; height: 28px; margin-left: 12px" />
	            </template>
	          </el-skeleton>
	        </div>
	        <div class="detail-body">
	          <div class="radar-section">
	            <el-skeleton animated :count="1">
	              <el-skeleton-item variant="rect" style="width: 100%; height: 360px; border-radius: 12px" />
	            </el-skeleton>
	          </div>
	          <div class="skills-section">
	            <el-skeleton animated :count="6" style="margin-bottom: 8px">
	              <el-skeleton-item variant="text" style="width: 100%; height: 32px" />
	            </el-skeleton>
	          </div>
	        </div>
	      </template>

	      <!-- 真实内容 -->
	      <template v-else>
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
	      </template>
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
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}

.page-header h2 {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  color: var(--foreground);
  margin: 0;
}

.header-sub {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
  margin: var(--space-1) 0 0;
}

.detail-body {
  display: flex;
  gap: var(--space-6);
}

.radar-section {
  flex: 0 0 420px;
}

.skills-section {
  flex: 1;
  min-width: 0;
}

.section-title {
  font-size: var(--font-size-base);
  font-weight: 500;
  color: var(--foreground);
  margin: 0 0 var(--space-3);
}
</style>
