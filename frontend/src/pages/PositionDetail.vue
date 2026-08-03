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
import { useJdStore } from '@/stores/jd'
import { chartColors } from '@/utils/chartTheme'

const jdStore = useJdStore()

const cc = chartColors()

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
const notFound = ref(false)

import { PROFICIENCY_MAP } from '@/utils/proficiency'

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
  project_management: '项目管理',
  design: '设计',
  domain: '领域知识',
  language: '语言',
  certification: '认证',
  methodology: '方法论',
}

const PROFICIENCY_TAG: Record<string, string> = {
  '精通': 'danger',
  '熟悉': 'warning',
  '了解': 'info',
}

// ── Hotness color: higher = greener, lower = grayer ──
function hotnessColor(count: number): string {
  if (count >= 8) return cc.success
  if (count >= 5) return cc.chart[4]   // lighter green from chart palette
  if (count >= 3) return cc.muted
  return cc.border
}

// ── 加载：按 id 单次拉取 ──
// get_position 已在后端做 PG→Neo4j 回退并返回 skills_required，故无需前端再发 Neo4j 优先请求
// （旧实现对含 `/` 的岗位名会 404，且与 PG 回退各弹一次 toast，叠加页面 toast = “一次报错弹多条”）。
// 改用列表传入的 id（UUID，路径安全）；silent=true 使真正缺失时不弹全局 404 toast，改渲染友好态。
let fetchToken = 0

onMounted(async () => {
  loading.value = true
  const myToken = ++fetchToken
  const id = positionName.value
  try {
    const d = (await jdStore.fetchPositionDetail(id, { silent: true })) as unknown as {
      name?: string
      name_cn?: string
      industry?: string
      description?: string
      skills_required?: SkillItem[]
    }
    if (myToken !== fetchToken) return
    if (!d || (!d.name && !d.name_cn)) {
      notFound.value = true
      return
    }
    position.value = {
      name: d.name_cn || d.name || id,
      industry: d.industry ?? '',
      description: d.description ?? '',
    }
    skills.value = (d.skills_required ?? []).map((s) => ({
      skill_id: s.skill_id ?? '',
      name: s.name ?? '',
      category: s.category ?? 'hard_skill',
      proficiency: s.proficiency ?? '熟悉',
      confidence: s.confidence ?? 1.0,
      source_count: s.source_count ?? 0,
    }))
  } catch {
    if (myToken !== fetchToken) return
    notFound.value = true // 真正缺失/404：友好态，不叠加 toast
  } finally {
    if (myToken === fetchToken) loading.value = false
  }
})
</script>

<template>
  <MainLayout>
    <div class="position-detail">
      <!-- 骨架屏加载态 -->
      <template v-if="loading">
        <div class="page-header">
          <el-skeleton
            :rows="0"
            animated
            style="width: 200px"
          >
            <template #template>
              <el-skeleton-item
                variant="circle"
                style="width: 32px; height: 32px"
              />
              <el-skeleton-item
                variant="text"
                style="width: 150px; height: 28px; margin-left: 12px"
              />
            </template>
          </el-skeleton>
        </div>
        <div class="detail-body">
          <div class="radar-section">
            <el-skeleton
              animated
              :count="1"
            >
              <el-skeleton-item
                variant="rect"
                style="width: 100%; height: 360px; border-radius: var(--radius-xl)"
              />
            </el-skeleton>
          </div>
          <div class="skills-section">
            <el-skeleton
              animated
              :count="6"
              style="margin-bottom: 8px"
            >
              <el-skeleton-item
                variant="text"
                style="width: 100%; height: 32px"
              />
            </el-skeleton>
          </div>
        </div>
      </template>

      <!-- 未找到：友好态（替代旧的“一次报错弹多条 toast”） -->
      <template v-else-if="notFound">
        <div class="page-header">
          <el-button
            circle
            :icon="ArrowLeft"
            size="small"
            @click="$router.push('/positions')"
          />
          <div>
            <h2>未找到该岗位</h2>
            <p class="header-sub">
              该岗位可能已下线、尚未同步，或链接已失效。
            </p>
          </div>
        </div>
        <div class="detail-body">
          <el-empty description="没有可展示的岗位信息">
            <el-button
              type="primary"
              @click="$router.push('/positions')"
            >
              返回岗位列表
            </el-button>
          </el-empty>
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
              :position-name="position?.name ?? positionName"
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
              empty-text="暂无数据"
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
                width="120"
              >
                <template #default="{ row }">
                  <div class="hotness-cell">
                    <el-progress
                      :percentage="Math.min(row.source_count / 10 * 100, 100)"
                      :stroke-width="8"
                      :color="hotnessColor(row.source_count)"
                      :show-text="false"
                      class="hotness-bar"
                    />
                    <span
                      class="hotness-badge"
                      :style="{ background: hotnessColor(row.source_count), color: '#fff' }"
                    >
                      {{ row.source_count }}
                    </span>
                  </div>
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

/* ── Hotness Cell ── */
.hotness-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.hotness-bar {
  flex: 1;
  min-width: 40px;
}
.hotness-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 18px;
  border-radius: 9px;
  font-size: 10px;
  font-weight: 700;
  padding: 0 5px;
  font-variant-numeric: tabular-nums;
}
</style>
