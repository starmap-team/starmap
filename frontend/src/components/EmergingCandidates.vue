<script setup lang="ts">
/**
 * 新兴岗位候选面板 — 模块A 新岗位发现（A4.1）
 *
 * 调用 POST /positions/discover 获取新兴演化候选岗位，展示：
 * 岗位名 + 涌现技能占比 + 涌现技能 + 岗位定义（可展开）。
 * 风格与演化看板页现有卡片一致（el-card / el-tag / el-progress / el-collapse）。
 */
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { api, type DiscoverCandidate } from '@/api/client'
import EmptyState from '@/components/EmptyState.vue'

const candidates = ref<DiscoverCandidate[]>([])
const loading = ref(false)
const status = ref('') // completed / insufficient_data / no_candidates / error
const backendMessage = ref('')

async function fetchCandidates(showErrorToast = false) {
  if (loading.value) return
  loading.value = true
  try {
    const res = await api.discoverPositions()
    candidates.value = res.emerging_positions ?? []
    status.value = res.status
    backendMessage.value = res.message ?? ''
  } catch (e: unknown) {
    status.value = 'error'
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    if (showErrorToast) {
      ElMessage.error(detail ?? '获取新兴岗位候选失败')
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void fetchCandidates(false) // 进页面自动加载，失败静默显示空态
})

// 候选岗位显示名：中文名优先（name_cn），后端未返回时保留 position
function candidateName(c: DiscoverCandidate): string {
  return c.name_cn || c.position_name_cn || c.position
}

// 涌现技能占比 → 百分比
function ratioPct(ratio: number): number {
  return Math.max(0, Math.min(100, Math.round(ratio * 100)))
}

// 占比颜色分级（与现有「新兴技能预警」的 涌现=danger/上升=warning 语义呼应）：
// ≥80% 高涌现（danger 红）→ ≥40% 中涌现（warning 橙）→ 其余（primary 蓝）
function ratioColor(ratio: number): string {
  if (ratio >= 0.8) return 'var(--danger, #f56c6c)'
  if (ratio >= 0.4) return 'var(--warning, #e6a23c)'
  return 'var(--primary, #409eff)'
}

// 空态文案：按接口状态区分，全部业务化中文（A4.3 文案友好化）
const emptyTitle = (): string => {
  if (status.value === 'insufficient_data') return '数据不足，暂无法发现'
  if (status.value === 'no_candidates') return '暂未发现新兴岗位候选'
  if (status.value === 'error') return '获取失败'
  return '暂无新兴岗位候选'
}
const emptyDescription = (): string => {
  if (status.value === 'error') return '请稍后重试，或点击右上角「重新发现」'
  return backendMessage.value || '当岗位的必备技能出现明显涌现信号时，会在此展示候选岗位'
}
</script>

<template>
  <el-card
    v-loading="loading"
    class="candidate-panel"
    shadow="hover"
  >
    <template #header>
      <div class="card-header-row">
        <span>新兴岗位候选</span>
        <el-tooltip
          placement="top"
          :show-after="300"
        >
          <template #content>
            <div class="ratio-tip">
              涌现技能占比 = 该岗位必备技能中属于「涌现/上升」技能的比例。<br>
              占比越高，代表该岗位越可能是正在兴起的新岗位。
            </div>
          </template>
          <el-tag
            v-if="candidates.length"
            type="danger"
            size="small"
            effect="plain"
          >
            {{ candidates.length }}
          </el-tag>
        </el-tooltip>
        <el-button
          class="refresh-btn"
          size="small"
          :loading="loading"
          :icon="Refresh"
          @click="fetchCandidates(true)"
        >
          重新发现
        </el-button>
      </div>
    </template>

    <!-- 候选卡片网格（与页面 emerging-grid 一致的 auto-fill 风格） -->
    <div
      v-if="candidates.length"
      class="candidate-grid"
    >
      <div
        v-for="c in candidates"
        :key="c.position"
        class="candidate-card"
      >
        <div class="candidate-name">{{ candidateName(c) }}</div>

        <!-- 涌现技能 -->
        <div class="candidate-skills">
          <span class="candidate-skills-label">涌现技能</span>
          <div class="candidate-skills-tags">
            <el-tag
              v-for="s in c.emerging_skills"
              :key="s"
              size="small"
              effect="plain"
              type="warning"
            >
              {{ s }}
            </el-tag>
          </div>
        </div>

        <!-- 涌现技能占比 -->
        <div class="candidate-ratio">
          <el-progress
            :percentage="ratioPct(c.emerging_ratio)"
            :color="ratioColor(c.emerging_ratio)"
            :stroke-width="8"
            :show-text="true"
          />
          <span class="candidate-ratio-label">涌现技能占比</span>
        </div>

        <!-- 岗位定义（可展开） -->
        <el-collapse class="candidate-def">
          <el-collapse-item
            :title="`查看岗位定义（共 ${c.definition.required_skills.length} 项必备技能）`"
            name="def"
          >
            <div class="def-block">
              <span class="def-label">必备技能：</span>
              <div class="def-tags">
                <el-tag
                  v-for="s in c.definition.required_skills"
                  :key="s"
                  size="small"
                  effect="plain"
                  :type="c.definition.emerging_required.includes(s) ? 'warning' : 'info'"
                  class="def-tag"
                >
                  {{ s }}
                </el-tag>
              </div>
              <p class="def-note">
                <span class="def-note-highlight">黄色</span> = 涌现/上升技能（该岗位成为新兴候选的关键）
              </p>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>

    <!-- 空态 -->
    <EmptyState
      v-else
      :title="emptyTitle()"
      :description="emptyDescription()"
    >
      <el-button
        size="small"
        type="primary"
        :loading="loading"
        @click="fetchCandidates(true)"
      >
        重新发现
      </el-button>
    </EmptyState>
  </el-card>
</template>

<style scoped>
.candidate-panel {
  margin-bottom: 16px;
}
.card-header-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.refresh-btn {
  margin-left: auto;
}
.ratio-tip {
  font-size: 12px;
  line-height: 1.7;
  max-width: 260px;
}

/* 候选卡片网格 — 与演化看板 emerging-grid 风格一致
   align-items: start：卡片高度独立，点击展开只影响当前卡片，
   同行其他卡片不被拉伸（避免"整行一起伸缩"的错觉） */
.candidate-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  align-items: start;
}
.candidate-card {
  border: 1px solid var(--border, #e4e7ed);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--card, #fff);
}
.candidate-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--foreground);
  margin-bottom: 10px;
  line-height: 1.4;
}

.candidate-skills {
  margin-bottom: 10px;
}
.candidate-skills-label {
  font-size: 11px;
  color: var(--muted-foreground);
  display: block;
  margin-bottom: 4px;
}
.candidate-skills-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.candidate-ratio {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.candidate-ratio .el-progress {
  flex: 1;
}
.candidate-ratio-label {
  font-size: 11px;
  color: var(--muted-foreground);
  white-space: nowrap;
}

.candidate-def :deep(.el-collapse-item__header) {
  font-size: 12px;
  color: var(--primary, #409eff);
  border-bottom: none;
}
.candidate-def :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}
.def-label {
  font-size: 12px;
  color: var(--muted-foreground);
  display: block;
  margin-bottom: 4px;
}
.def-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.def-note {
  font-size: 11px;
  color: var(--muted-foreground);
  margin: 8px 0 0;
}
.def-note-highlight {
  color: var(--warning, #e6a23c);
  font-weight: 600;
}
</style>
