<script setup lang="ts">
/**
 * 岗位详情页 — 能力雷达图 + 技能列表
 * 路由：/position/:name
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import SkillRadar, { type RadarItem } from '@/components/SkillRadar.vue'
import { useJdStore } from '@/stores/jd'
import { chartColors } from '@/utils/chartTheme'
import { freshnessOf, type FreshnessInfo } from '@/utils/freshness'

const jdStore = useJdStore()

const cc = chartColors()

const route = useRoute()
const router = useRouter()
const positionName = computed(() => route.params.name as string)

// ── 数据 ──
interface SkillItem {
  skill_id: string
  name: string
  name_cn?: string  // D8i: 技能中文名
  category: string
  proficiency: string
  confidence: number | null
  source_count: number
}

interface PositionInfo {
  name: string
  industry: string
  description: string
 // PLAN-006④: 岗位入库时间, 用于"数据时效"指示; null = 演示/无采集
  discovered_at: string | null
}

const position = ref<PositionInfo | null>(null)
const skills = ref<SkillItem[]>([])
const loading = ref(false)
const notFound = ref(false)

import { PROFICIENCY_MAP } from '@/utils/proficiency'
import { CATEGORY_LABELS } from '@/constants/labels'

// ── 雷达图数据 ──
const radarData = computed<RadarItem[]>(() =>
  skills.value.map(s => ({
    skill: s.name,
    required: PROFICIENCY_MAP[s.proficiency] ?? 0.5,
    user: 0, // 岗位详情仅展示要求，无用户对比
  }))
)

//: 技能画像缺失降级判定。岗位存在但无技能关系时不走 404，
// 改为渲染「暂无技能画像」引导卡片（沿：无画像岗位 → 200 + 诚实空态）。
const hasSkillProfile = computed(() => skills.value.length > 0)

const PROFICIENCY_TAG: Record<string, string> = {
  '精通': 'danger',
  '熟悉': 'warning',
  '了解': 'info',
}

// PLAN-006④: 数据时效指示 (discovered_at → 友好标签 + tag 类型, 逻辑收敛于 utils/freshness)
const freshness = computed<FreshnessInfo>(() => freshnessOf(position.value?.discovered_at))

// ── Hotness color: higher = greener, lower = grayer ──
function hotnessColor(count: number): string {
  if (count >= 8) return cc.success
  if (count >= 5) return cc.chart[4]   // lighter green from chart palette
  if (count >= 3) return cc.muted
  return cc.border
}

// QA 优化: 详情页直达「匹配诊断」——携带岗位名，匹配页确认技能后自动选中该岗位
function goMatch() {
  const name = position.value?.name ?? (positionName.value as string)
  if (!name) { ElMessage.warning('岗位信息未加载完成'); return }
  router.push({ path: '/match', query: { position: name } })
}

// ── 加载：按 id 单次拉取 ──
// get_position 已在后端做 PG→Neo4j 回退并返回 skills_required，故无需前端再发 Neo4j 优先请求
// （旧实现对含 `/` 的岗位名会 404，且与 PG 回退各弹一次 toast，叠加页面 toast = “一次报错弹多条”）。
// 改用列表传入的 id（UUID，路径安全）；silent=true 使真正缺失时不弹全局 404 toast，改渲染友好态。
let fetchToken = 0

//-AUDIT-FIX (02-01): `/position/A` ↔ `/position/B` 复用同一组件实例时
// onMounted 不会重跑，旧岗位的 skills/radar 会残留。提取为函数并 watch
// route.params.name 触发重拉（fetchToken 竞态防护沿用）。
async function loadPosition() {
  loading.value = true
  notFound.value = false  // M2-AUDIT-FIX: 路由切换重拉前复位，避免上次 not-found 残留
  const myToken = ++fetchToken
  const id = positionName.value
  try {
    const d = (await jdStore.fetchPositionDetail(id, { silent: true })) as unknown as {
      name?: string
      name_cn?: string
      industry?: string
      description?: string
      skills_required?: SkillItem[]
      discovered_at?: string | null
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
 // PLAN-006④: 岗位入库时间, 用于"数据时效"指示
      discovered_at: d.discovered_at ?? null,
    }
    skills.value = (d.skills_required ?? []).map((s) => ({
      skill_id: s.skill_id ?? '',
      name: s.name ?? '',
      name_cn: s.name_cn ?? '',  // D8i: 技能中文名
      category: s.category ?? 'hard_skill',
      proficiency: s.proficiency ?? '熟悉',
 // PLAN-006③ 红线: 后端无置信度时不再编造 1.0, 显示"未评估"
      confidence: s.confidence ?? null,
      source_count: s.source_count ?? 0,
    }))
  } catch {
    if (myToken !== fetchToken) return
    notFound.value = true // 真正缺失/404：友好态，不叠加 toast
  } finally {
    if (myToken === fetchToken) loading.value = false
  }
}

onMounted(loadPosition)
watch(() => route.params.name, loadPosition)
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
          <el-button
            type="primary"
            size="small"
            @click="goMatch"
          >
            匹配诊断
          </el-button>
          <div>
            <h2>{{ position?.name ?? positionName }}</h2>
            <p class="header-sub">
              {{ position?.industry ?? '' }}
            </p>
            <!-- PLAN-006④: 数据时效指示 (演示数据 / 数据更新于 X / 较旧) -->
            <el-tag
              :type="freshness.type"
              size="small"
              effect="plain"
              class="freshness-tag"
            >
              {{ freshness.label }}
            </el-tag>
          </div>
        </div>

        <div class="detail-body">
          <!-- 左侧：雷达图 / 缺技能降级 -->
          <section class="radar-section">
            <SkillRadar
              v-if="hasSkillProfile"
              :data="radarData"
              :position-name="position?.name ?? positionName"
            />
            <!--: 岗位存在但无技能画像 → 诚实空态 + 引导，不返回 404 -->
            <el-card
              v-else
              class="no-profile-card"
              shadow="never"
            >
              <div class="no-profile-body">
                <div class="no-profile-icon">
                  <svg
                    width="44"
                    height="44"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" />
                    <line
                      x1="12"
                      y1="2"
                      x2="12"
                      y2="22"
                    />
                  </svg>
                </div>
                <p class="no-profile-title">
                  暂无技能画像
                </p>
                <p class="no-profile-hint">
                  该岗位已入库，但尚未抽取到技能要求，因此无法绘制能力雷达图。
                  可从一份 JD 中抽取技能后再回来查看。
                </p>
                <div class="no-profile-actions">
                  <el-button
                    type="primary"
                    @click="$router.push('/extract')"
                  >
                    前往 JD 抽取
                  </el-button>
                  <el-button @click="$router.push('/positions')">
                    返回岗位列表
                  </el-button>
                </div>
              </div>
            </el-card>
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
              empty-text="暂无技能画像，可从 JD 抽取后回看"
            >
              <el-table-column
                prop="name"
                label="技能"
                min-width="120"
              >
                <!--: 技能中文名优先展示 -->
                <template #default="{ row }">
                  {{ row.name_cn || row.name }}
                </template>
              </el-table-column>
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
                  {{ row.confidence == null ? '未评估' : `${(row.confidence * 100).toFixed(0)}%` }}
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

/* ──: 无技能画像降级卡片 ── */
.no-profile-card {
  border: 1px dashed var(--border);
  border-radius: var(--radius-xl);
  min-height: 360px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.no-profile-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--space-4) var(--space-2);
}
.no-profile-icon {
  color: var(--muted-foreground);
  opacity: 0.4;
  margin-bottom: var(--space-3);
}
.no-profile-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--foreground);
  margin: 0 0 var(--space-2);
}
.no-profile-hint {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  line-height: 1.6;
  margin: 0 0 var(--space-4);
}
.no-profile-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  justify-content: center;
}

/* ── Hotness Cell ── */.hotness-cell {
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
