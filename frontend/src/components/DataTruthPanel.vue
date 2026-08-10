<script setup lang="ts">
/**
 * 数据源真理面板 — Phase 4 P0
 *
 * 显示每个 KPI 数字的三层来源对比：API / PostgreSQL / Neo4j
 * 让管理员看到 70/56/39 这三个数字的真实含义
 */
import { onMounted, ref } from 'vue'
import { CircleCheck, WarningFilled, CircleClose } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

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
    message: 'Reconcile 任务已提交，正在同步 PG ↔ Neo4j...',
    type: 'info',
    duration: 0,  // 永驻, 完成后手动关闭
  })
  try {
    const result = await request.post('/admin/reconcile-neo4j') as {
      health?: string
      positions_in_neo4j?: number
      skills_in_neo4j?: number
      positions_in_pg?: number
      skills_in_pg?: number
      orphans_pruned?: number
      duration_ms?: number
    }
    await loadReport()
    const elapsed = ((Date.now() - start) / 1000).toFixed(1)
    ElMessage.success(
      `Reconcile 完成 (${elapsed}s) · Neo4j 节点=${result.positions_in_neo4j ?? '?'}/${result.skills_in_neo4j ?? '?'} · PG 节点=${result.positions_in_pg ?? '?'}/${result.skills_in_pg ?? '?'} · 孤儿清理=${result.orphans_pruned ?? 0} · 健康度=${result.health ?? '?'}`,
    )
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : 'Reconcile 失败'
    ElMessage.error(`Reconcile 失败: ${errorMsg.value}`)
  } finally {
    progressMsg.close()
    reconcileLoading.value = false
  }
}

onMounted(loadReport)

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
        每个 KPI 数字都有三层来源：API 返回值、PostgreSQL 直查、Neo4j 直查。
        差异超过 1% 标记为 <el-tag
          type="warning"
          size="small"
        >
          warn
        </el-tag>，
        差异超过 10% 标记为 <el-tag
          type="danger"
          size="small"
        >
          critical
        </el-tag>。
      </p>

      <div
        v-if="report.health"
        class="health-card"
      >
        <h4>同步健康度（Phase 5 Step 4）</h4>
        <div class="health-row">
          <div class="health-item">
            <span class="health-label">孤儿 Position</span>
            <el-tag
              :type="report.health.orphan_positions === 0 ? 'success' : 'danger'"
              size="small"
            >
              {{ report.health.orphan_positions }}
            </el-tag>
          </div>
          <div class="health-item">
            <span class="health-label">孤儿 Skill</span>
            <el-tag
              :type="report.health.orphan_skills === 0 ? 'success' : 'danger'"
              size="small"
            >
              {{ report.health.orphan_skills }}
            </el-tag>
          </div>
          <div class="health-item">
            <span class="health-label">同步健康度</span>
            <el-tag
              :type="report.health.sync_health === 'ok' ? 'success' : report.health.sync_health === 'warn' ? 'warning' : 'danger'"
              size="small"
            >
              {{ report.health.sync_health }}
            </el-tag>
          </div>
          <div class="health-item">
            <span class="health-label">最近 reconcile</span>
            <el-tag
              :type="report.health.reconcile_status === 'ok' ? 'success' : report.health.reconcile_status === 'warn' ? 'warning' : 'danger'"
              size="small"
            >
              {{ report.health.reconcile_status }}
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
              立即执行一次 PG ↔ Neo4j 双向对账：<br>
              • 把 position_records / skill_records 投影到 Neo4j<br>
              • 清理 Neo4j 中的孤儿节点<br>
              • 重新计算三层口径 KPI 差异<br>
              <br>
              通常 30-60 秒。系统每天凌晨 3 点也会自动跑。
            </template>
            <el-button
              size="small"
              type="primary"
              :loading="reconcileLoading"
              @click="triggerReconcile"
            >
              手动触发 reconcile
            </el-button>
          </el-tooltip>
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
          label="PostgreSQL"
          width="110"
        >
          <template #default="{ row }">
            <span class="pg-value">{{ row.postgres_value }}</span>
          </template>
        </el-table-column>

        <el-table-column
          label="Neo4j"
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
</style>