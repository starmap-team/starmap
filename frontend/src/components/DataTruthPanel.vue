<script setup lang="ts">
/**
 * 数据源真理面板 — P0
 *
 * 显示每个 KPI 数字的三层来源对比：API / PostgreSQL / Neo4j
 * 让管理员看到 70/56/39 这三个数字的真实含义
 */
import { onMounted, ref } from 'vue'
import { CircleCheck, WarningFilled, CircleClose } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

// 2026-08-12 (admin 联调): 向父级上报整体诊断状态，供 banner 类型动态化
// （此前 Admin.vue 的 banner 硬编码 type="error"，报告全 ok 也显示 ERROR）
const emit = defineEmits<{
  (e: 'overall-status', status: 'ok' | 'warn' | 'critical'): void
}>()

interface TruthRow {
  metric: string
  description: string
  api_value: number
  postgres_value: number
  neo4j_value: number
  diff_pct: number
  status: 'ok' | 'warn' | 'critical'
  explanation: string
}

interface HealthMetrics {
  orphan_positions: number
  orphan_skills: number
  // 2026-08-21 (debug 修复): unlinked 半孤立（Neo4j 有 + PG 有 + 缺 canonical_id）
  unlinked_positions: number
  unlinked_skills: number
  last_reconcile_at: string | null
  reconcile_status: 'ok' | 'warn' | 'critical' | 'unknown'
  sync_health: 'ok' | 'warn' | 'critical'
}

interface TruthReport {
  rows: TruthRow[]
  health: HealthMetrics
  generated_at: string
}

const report = ref<TruthReport | null>(null)
const loading = ref(false)
const reconcileLoading = ref(false)
const errorMsg = ref<string | null>(null)

// 整体状态 = 各指标行 + 同步健康度 中最差的一档（ok < warn < critical）
function emitOverallStatus() {
  if (!report.value) return
  const rank: Record<string, number> = { ok: 0, warn: 1, critical: 2 }
  let worst: 'ok' | 'warn' | 'critical' = 'ok'
  for (const r of report.value.rows || []) {
    const s = r.status as 'ok' | 'warn' | 'critical'
    if ((rank[s] ?? 0) > rank[worst]) worst = s
  }
  const health = report.value.health
  if (health) {
    for (const s of [health.sync_health, health.reconcile_status]) {
      const key = s as 'ok' | 'warn' | 'critical'
      if (key && (rank[key] ?? 0) > rank[worst]) worst = key
    }
  }
  emit('overall-status', worst)
}

async function loadReport(silent = false) {
  loading.value = true
  errorMsg.value = null
  try {
    report.value = (await request.get('/admin/data-truth')) as TruthReport
 // E7 fix: surface real-time data status. The numbers, the diffs, the
 // "explanation" column, and the "生成时间" are all generated server-side
 // per request (60s Redis cache). Make the freshness visible by
 // stamping the load time and the cache status into the report header.
    if (report.value) {
      (report.value as any).__clientLoadedAt = new Date().toISOString()
    }
    emitOverallStatus()
    if (!silent) {
      ElMessage.success('诊断报告已刷新')
    }
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '加载数据源诊断失败'
    ElMessage.error(errorMsg.value)
  } finally {
    loading.value = false
  }
}

async function triggerReconcile() {
  reconcileLoading.value = true
  const start = Date.now()
 // E6 fix: provide immediate feedback so the admin knows the action was
 // registered. A 30-60s reconcile that appears silent makes the user
 // think the button is broken.
  const progressMsg = ElMessage({
    message: '对账任务已提交，正在同步主数据与图谱...',
    type: 'info',
    duration: 0,  // 永驻, 完成后手动关闭
  })
  try {
    // 2026-08-28 (数据源诊断超时根治): reconcile 全量对账 30s 前端默认超时不够,
    // 覆盖为 90s（后端已改增量边对账，正常 <10s；极端情况留余量）。
    const result = await request.post('/admin/reconcile-neo4j', undefined, { timeout: 90000 }) as {
      health?: string
      positions_in_neo4j?: number
      skills_in_neo4j?: number
      positions_in_pg?: number
      skills_in_pg?: number
      orphans_pruned?: number
      unlinked_linked?: number
      duration_ms?: number
    }
    await loadReport()
    const elapsed = ((Date.now() - start) / 1000).toFixed(1)
    ElMessage.success(
      `对账完成（${elapsed} 秒）· 图谱岗位/技能节点 ${result.positions_in_neo4j ?? '?'}/${result.skills_in_neo4j ?? '?'} · 主数据岗位/技能 ${result.positions_in_pg ?? '?'}/${result.skills_in_pg ?? '?'} · 清理孤立节点 ${result.orphans_pruned ?? 0} · 链接半孤立 ${result.unlinked_linked ?? 0} · 健康度 ${result.health ?? '?'}`,
    )
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '对账失败'
    ElMessage.error(`对账失败：${errorMsg.value}`)
  } finally {
    progressMsg.close()
    reconcileLoading.value = false
  }
}

onMounted(() => {
  loadReport()
  loadOrphanQueue()
})

// ── P2 孤儿节点审批队列 ──
interface OrphanQueueItem {
  id: string
  node_type: 'position' | 'skill'
  name: string
  canonical_id: string | null
  reason: 'no_canonical_id' | 'orphan_canonical_id'
  status: 'pending' | 'approved' | 'rejected' | 'cleaned'
  detail: Record<string, unknown>
  created_at: string | null
  reviewed_at: string | null
  reviewed_by: string | null
}
const orphanItems = ref<OrphanQueueItem[]>([])
const orphanLoading = ref(false)
const approvingId = ref<string | null>(null)

async function loadOrphanQueue() {
  orphanLoading.value = true
  try {
    const data = await request.get('/admin/orphan-queue') as {
      items: OrphanQueueItem[]
      total: number
    }
    orphanItems.value = data.items ?? []
  } catch {
    orphanItems.value = []
  } finally {
    orphanLoading.value = false
  }
}

// approve = 删除孤儿节点（级联边）+ 审计；reject = 拒绝清理
async function actOnOrphan(item: OrphanQueueItem, action: 'approve' | 'reject') {
  approvingId.value = item.id
  try {
    await request.post(`/admin/orphan-queue/${item.id}/action`, { action })
    ElMessage.success(
      action === 'approve'
        ? `已清理孤立${item.node_type === 'position' ? '岗位' : '技能'}「${item.name}」`
        : `已拒绝清理「${item.name}」`,
    )
    await loadOrphanQueue()
    await loadReport(true)  // 清理后刷新报告（总数差异应归 0）
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '操作失败'
    ElMessage.error(`孤立节点处理失败: ${msg}`)
  } finally {
    approvingId.value = null
  }
}

function orphanTypeLabel(t: string): string {
  return t === 'position' ? '岗位' : '技能'
}

// 语义级原因标签（区分: 无引用=可删除孤儿 / 被引用=同实体待链接或 PG 缺记录）
function orphanReasonText(row: { reason: string; detail?: Record<string, unknown> }): string {
  const ref = Number(row.detail?.referenced_by ?? 0)
  if (row.reason === 'no_canonical_id') {
    return ref > 0 ? '缺唯一标识·被引用' : '缺唯一标识'
  }
  return 'PG 无对应记录'
}

// 语义级状态映射（P2 优化: 不向用户暴露 raw enum）
const ORPHAN_STATUS_LABEL: Record<string, string> = {
  pending: '待审批',
  approved: '已批准',
  rejected: '已拒绝',
  cleaned: '已清理',
  linked: '已链接',
}
const ORPHAN_STATUS_TYPE: Record<string, 'warning' | 'success' | 'info' | 'danger'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'info',
  cleaned: 'success',
  linked: 'success',
}
function orphanStatusLabel(status: string): string {
  return ORPHAN_STATUS_LABEL[status] ?? status
}
function orphanStatusType(status: string): 'warning' | 'success' | 'info' | 'danger' {
  return ORPHAN_STATUS_TYPE[status] ?? 'info'
}

// 健康/同步状态语义化
function healthStatusLabel(status: string | undefined): string {
  const map: Record<string, string> = { ok: '正常', warn: '轻微异常', critical: '严重异常', unknown: '未知' }
  return map[status ?? ''] ?? (status ?? '未知')
}

// 批量批准无引用孤儿（删除安全，一次调用）
const batchLoading = ref(false)
async function batchApproveSafe() {
  batchLoading.value = true
  try {
    const result = await request.post('/admin/orphan-queue/batch-action', {
      action: 'approve',
      only_no_reference: true,
    }) as { processed: number; deleted: number; errors?: string[] }
    ElMessage.success(
      `批量清理完成：处理 ${result.processed} 项，删除 ${result.deleted} 个孤立节点` +
      (result.errors?.length ? `（${result.errors.length} 项失败）` : ''),
    )
    await loadOrphanQueue()
    await loadReport(true)
  } catch (e: unknown) {
    ElMessage.error(`批量清理失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    batchLoading.value = false
  }
}

// P3a: 确认链接 — 把无 canonical_id 节点 SET 到建议的 PG 记录（非破坏、可逆）
const linkingId = ref<string | null>(null)
async function linkOrphan(item: OrphanQueueItem) {
  linkingId.value = item.id
  try {
    await request.post(`/admin/orphan-queue/${item.id}/link`, {})
    ElMessage.success(`已链接「${item.name}」到 PG 记录「${item.detail?.suggested_name ?? ''}」`)
    await loadOrphanQueue()
    await loadReport(true)
  } catch (e: unknown) {
    ElMessage.error(`链接失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    linkingId.value = null
  }
}

// 链接建议置信度语义
function suggestionLabel(level: string | undefined): string {
  const map: Record<string, string> = { exact: '精确匹配', normalized: '归一化匹配', fuzzy: '模糊候选' }
  return map[level ?? ''] ?? ''
}

function statusColor(status: string): string {
  if (status === 'ok') return 'success'
  if (status === 'warn') return 'warning'
  return 'danger'
}

function statusLabel(status: string): string {
  if (status === 'ok') return '一致'
  if (status === 'warn') return '轻微差异'
  return '严重差异'
}

function statusIcon(status: string): unknown {
  if (status === 'ok') return CircleCheck
  if (status === 'warn') return WarningFilled
  return CircleClose
}
</script>

<template>
  <div class="data-truth-panel">
    <el-alert
      v-if="errorMsg"
      type="error"
      :title="errorMsg"
      :closable="false"
      show-icon
    />

    <div
      v-if="report"
      class="truth-container"
    >
      <div class="truth-header">
        <h3>数据源诊断报告</h3>
        <div class="header-actions">
          <span class="generated-at">
            服务端生成: {{ report.generated_at }}
            <span
              v-if="(report as any).__clientLoadedAt"
              class="client-load-time"
            >
              · 客户端加载: {{ (report as any).__clientLoadedAt }}
            </span>
          </span>
          <el-button @click="loadReport">
            刷新
          </el-button>
        </div>
      </div>

      <p class="truth-intro">
        每个统计数字都有多层来源相互校验。
        差异超过 1% 标记为 <el-tag
          type="warning"
          size="small"
        >
          警告
        </el-tag>，
        差异超过 10% 标记为 <el-tag
          type="danger"
          size="small"
        >
          严重
        </el-tag>。
      </p>

      <div
        v-if="report.health"
        class="health-card"
      >
        <h4>同步健康度</h4>
        <div class="health-row">
          <div class="health-item">
            <span class="health-label">孤立岗位</span>
            <el-tag
              :type="report.health.orphan_positions === 0 ? 'success' : 'danger'"
              size="small"
            >
              {{ report.health.orphan_positions }}
            </el-tag>
          </div>
          <div class="health-item">
            <span class="health-label">孤立技能</span>
            <el-tag
              :type="report.health.orphan_skills === 0 ? 'success' : 'danger'"
              size="small"
            >
              {{ report.health.orphan_skills }}
            </el-tag>
          </div>
          <!-- 2026-08-21 (debug 修复): 半孤立（Neo4j 有 + PG 有 + 缺 canonical_id）
               此前不显示导致「孤立 0」与「队列 23 pending」看似矛盾。 -->
          <div class="health-item">
            <span
              class="health-label"
              title="半孤立：知识图谱中已有节点但缺少唯一标识，未关联到数据库"
            >半孤立岗位</span>
            <el-tag
              :type="report.health.unlinked_positions === 0 ? 'success' : 'warning'"
              size="small"
            >
              {{ report.health.unlinked_positions }}
            </el-tag>
          </div>
          <div class="health-item">
            <span
              class="health-label"
              title="半孤立：知识图谱中已有节点但缺少唯一标识，未关联到数据库"
            >半孤立技能</span>
            <el-tag
              :type="report.health.unlinked_skills === 0 ? 'success' : 'warning'"
              size="small"
            >
              {{ report.health.unlinked_skills }}
            </el-tag>
          </div>
          <div class="health-item">
            <span class="health-label">同步健康度</span>
            <el-tag
              :type="report.health.sync_health === 'ok' ? 'success' : report.health.sync_health === 'warn' ? 'warning' : 'danger'"
              size="small"
            >
              {{ healthStatusLabel(report.health.sync_health) }}
            </el-tag>
          </div>
          <div class="health-item">
            <span class="health-label">最近 reconcile</span>
            <el-tag
              :type="report.health.reconcile_status === 'ok' ? 'success' : report.health.reconcile_status === 'warn' ? 'warning' : 'danger'"
              size="small"
            >
              {{ healthStatusLabel(report.health.reconcile_status) }}
            </el-tag>
          </div>
          <div class="health-item">
            <span class="health-label">时间</span>
            <span class="health-time">{{ report.health.last_reconcile_at ?? '尚未运行' }}</span>
          </div>
        </div>
        <div class="health-actions">
          <el-tooltip
            placement="top"
            :show-after="200"
          >
            <template #content>
              立即执行一次双向数据对账：<br>
              • 把岗位、技能同步到图谱<br>
              • 清理图谱中的孤立节点<br>
              • 重新计算多层口径 KPI 差异<br>
              <br>
              通常 30-60 秒。系统每天凌晨 3 点也会自动跑。
            </template>
            <el-button
              size="small"
              type="primary"
              :loading="reconcileLoading"
              @click="triggerReconcile"
            >
              立即对账并修复
            </el-button>
          </el-tooltip>
        </div>
      </div>

      <!-- 孤立节点审批队列（删除是破坏性操作，必须经审批门控） -->
      <div class="orphan-card">
        <div class="orphan-header">
          <h4>孤立节点清理队列</h4>
          <span class="orphan-hint">
            孤立节点 = 图谱中存在但主数据中没有对应记录。
            批准后执行删除（级联边），操作记入审计日志。
          </span>
          <el-tooltip
            placement="top"
            :show-after="200"
          >
            <template #content>
              一键批准清理所有「无被引用关系」的孤立节点（删除安全、可审计）。<br>
              被其他节点引用的孤立节点保持待处理，需先人工处理引用关系。
            </template>
            <el-button
              size="small"
              type="primary"
              :loading="batchLoading"
              :disabled="!orphanItems.some(i => i.status === 'pending' && Number(i.detail?.referenced_by ?? 0) === 0)"
              @click="batchApproveSafe"
            >
              批量批准无引用孤儿
            </el-button>
          </el-tooltip>
        </div>
        <el-table
          v-loading="orphanLoading"
          :data="orphanItems"
          size="small"
          empty-text="暂无孤儿待清理 —— 双库已一致 🎉"
        >
          <el-table-column
            label="类型"
            width="70"
          >
            <template #default="{ row }">
              <el-tag
                :type="row.node_type === 'position' ? 'primary' : 'success'"
                size="small"
              >
                {{ orphanTypeLabel(row.node_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="名称"
            min-width="160"
            prop="name"
            show-overflow-tooltip
          />
          <el-table-column
            label="原因"
            width="150"
          >
            <template #default="{ row }">
              <span :class="{ 'ref-warn': Number(row.detail?.referenced_by ?? 0) > 0 }">
                {{ orphanReasonText(row) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            label="被引用边"
            width="90"
          >
            <template #default="{ row }">
              <span :class="{ 'ref-warn': Number(row.detail?.referenced_by ?? 0) > 0 }">
                {{ row.detail?.referenced_by ?? 0 }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            label="链接建议"
            min-width="150"
          >
            <template #default="{ row }">
              <template v-if="row.detail?.suggested_cid">
                <span class="suggestion-name">{{ row.detail.suggested_name }}</span>
                <el-tag
                  :type="row.detail.suggestion_level === 'exact' ? 'success' : row.detail.suggestion_level === 'normalized' ? 'primary' : 'warning'"
                  size="small"
                  class="suggestion-tag"
                >
                  {{ suggestionLabel(row.detail.suggestion_level) }}
                </el-tag>
              </template>
              <span
                v-else
                class="orphan-muted"
              >
                —
              </span>
            </template>
          </el-table-column>
          <el-table-column
            label="状态"
            width="90"
          >
            <template #default="{ row }">
              <el-tag
                :type="orphanStatusType(row.status)"
                size="small"
              >
                {{ orphanStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="操作"
            width="220"
          >
            <template #default="{ row }">
              <template v-if="row.status === 'pending'">
                <el-popconfirm
                  :title="`确认删除孤儿${orphanTypeLabel(row.node_type)}「${row.name}」？（级联移除相关边，不可恢复）`"
                  width="260"
                  @confirm="actOnOrphan(row, 'approve')"
                >
                  <template #reference>
                    <el-button
                      size="small"
                      type="danger"
                      :loading="approvingId === row.id"
                      :disabled="Number(row.detail?.referenced_by ?? 0) > 0"
                    >
                      批准删除
                    </el-button>
                  </template>
                </el-popconfirm>
                <el-button
                  v-if="row.detail?.suggested_cid"
                  size="small"
                  type="primary"
                  plain
                  :loading="linkingId === row.id"
                  @click="linkOrphan(row)"
                >
                  确认链接
                </el-button>
                <el-button
                  size="small"
                  :loading="approvingId === row.id"
                  @click="actOnOrphan(row, 'reject')"
                >
                  拒绝
                </el-button>
              </template>
              <span
                v-else
                class="orphan-muted"
              >
                {{ row.reviewed_by ? `${row.reviewed_by} ${row.reviewed_at?.slice(0, 10) ?? ''}` : '—' }}
              </span>
            </template>
          </el-table-column>
        </el-table>
        <div
          v-if="orphanItems.some(i => Number(i.detail?.referenced_by ?? 0) > 0)"
          class="orphan-note"
        >
          ⚠ 被引用边的孤儿已禁用「批准删除」：它们很可能是<b>同一实体的不同写法</b>
          （如 React.js↔React）或<b>历史抽取未同步到数据库的技能</b>——应核对数据库记录后
          「关联唯一标识」或补录，而非删除（删除会破坏学习路径的技能前置关系）。
        </div>
      </div>

      <el-table
        v-loading="loading"
        :data="report.rows"
        stripe
        size="default"
        empty-text="暂无数据"
      >
        <el-table-column
          label="指标"
          min-width="120"
        >
          <template #default="{ row }">
            <span class="metric-name">{{ row.metric }}</span>
          </template>
        </el-table-column>

        <el-table-column
          label="API 返回"
          width="100"
        >
          <template #default="{ row }">
            <span class="api-value">{{ row.api_value }}</span>
          </template>
        </el-table-column>

        <el-table-column
          label="主数据库"
          width="110"
        >
          <template #default="{ row }">
            <span class="pg-value">{{ row.postgres_value }}</span>
          </template>
        </el-table-column>

        <el-table-column
          label="图谱"
          width="100"
        >
          <template #default="{ row }">
            <span class="neo4j-value">{{ row.neo4j_value }}</span>
          </template>
        </el-table-column>

        <el-table-column
          label="差异"
          width="120"
        >
          <template #default="{ row }">
            <el-tag
              :type="statusColor(row.status)"
              size="small"
            >
              {{ row.diff_pct }}%
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column
          label="状态"
          width="120"
        >
          <template #default="{ row }">
            <el-icon
              :size="16"
              :color="row.status === 'ok' ? '#16a34a' : row.status === 'warn' ? '#f59e0b' : '#dc2626'"
            >
              <component :is="statusIcon(row.status)" />
            </el-icon>
            {{ statusLabel(row.status) }}
          </template>
        </el-table-column>

        <el-table-column
          label="说明"
          min-width="400"
        >
          <template #default="{ row }">
            <span class="explanation">{{ row.explanation }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.data-truth-panel {
  padding: var(--space-4);
}

.truth-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.truth-header h3 {
  margin: 0;
  font-size: var(--font-size-xl);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.client-load-time {
  color: var(--muted-foreground);
  font-style: italic;
  margin-left: 4px;
}

.generated-at {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
}

.truth-intro {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  margin-bottom: var(--space-4);
  line-height: 1.6;
}

.metric-name {
  font-weight: 600;
  color: var(--foreground);
}

.api-value,
.pg-value,
.neo4j-value {
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.api-value {
  color: var(--info);
}

.pg-value {
  color: var(--primary);
}

.neo4j-value {
  color: var(--success);
}

.explanation {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  line-height: 1.5;
}

.health-card {
  background: color-mix(in srgb, var(--primary) 3%, var(--card));
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
}

.health-card h4 {
  margin: 0 0 var(--space-3) 0;
  font-size: var(--font-size-base);
  font-weight: 600;
}

.health-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  align-items: center;
}

.health-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.health-label {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
}

.health-time {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
}

.health-actions {
  margin-top: var(--space-3);
  display: flex;
  gap: var(--space-2);
}

/* P2 孤儿审批队列 */
.orphan-card {
  margin-top: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--surface-card);
}

.orphan-header {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.orphan-header h4 {
  margin: 0;
  font-size: var(--font-size-sm);
}

.orphan-hint {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

.ref-warn {
  color: var(--danger);
  font-weight: 600;
}

.orphan-note {
  margin-top: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--warning);
}

.orphan-muted {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

/* P3a 链接建议 */
.suggestion-name {
  font-size: var(--font-size-xs);
  margin-right: 4px;
}

.suggestion-tag {
  margin-top: 2px;
}
</style>