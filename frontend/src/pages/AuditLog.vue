<script setup lang="ts">
/**
 * Audit Log viewer — admin-only.
 *
 * Reads from `audit_events` table via:
 *   GET /admin/audit-events?actor=&event=&from=&to=&page=&page_size=
 */
import { onMounted, ref, reactive } from 'vue'
import request from '@/api/request'

interface AuditRow {
  id: string
  event: string
  actor: string
  action: string
  detail: string
  ip: string
  created_at: string
}

const loading = ref(false)
const items = ref<AuditRow[]>([])
const total = ref(0)

const filters = reactive({
  actor: '',
  event: '',
  from: '',
  to: '',
  page: 1,
  page_size: 50,
})

const EVENT_TYPE_LABELS: Record<string, { label: string; type: 'primary' | 'success' | 'info' | 'warning' | 'danger' }> = {
  auth_failure: { label: '认证失败', type: 'danger' },
  authz_denied: { label: '权限拒绝', type: 'warning' },
  rate_limited: { label: '速率限制', type: 'warning' },
  token_invalid: { label: '令牌无效', type: 'danger' },
  token_expired: { label: '令牌过期', type: 'info' },
  sensitive_read: { label: '敏感读取', type: 'info' },
  sensitive_write: { label: '敏感写入', type: 'warning' },
  file_upload: { label: '文件上传', type: 'info' },
  admin_action: { label: '管理操作', type: 'primary' },
  login_locked: { label: '账号锁定', type: 'danger' },
  login_success: { label: '登录成功', type: 'success' },
  password_changed: { label: '密码修改', type: 'warning' },
  password_reset: { label: '密码重置', type: 'warning' },
  user_created: { label: '用户创建', type: 'success' },
  user_updated: { label: '用户更新', type: 'info' },
  user_disabled: { label: '用户停用', type: 'danger' },
  user_unlocked: { label: '用户解锁', type: 'success' },
  account_deleted: { label: '账号删除', type: 'danger' },
}

async function fetchList() {
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      page: filters.page,
      page_size: filters.page_size,
    }
    if (filters.actor) params.actor = filters.actor
    if (filters.event) params.event = filters.event
    if (filters.from) params.from_ts = new Date(filters.from).toISOString()
    if (filters.to) {
      // Allow selecting "to the end of the day" by adding 24h if only date provided
      const toDate = new Date(filters.to)
      if (filters.to.length <= 10) toDate.setHours(23, 59, 59, 999)
      params.to_ts = toDate.toISOString()
    }
    const data = (await request.get('/admin/audit-events', { params })) as {
      total: number
      items: AuditRow[]
    }
    items.value = data.items
    total.value = data.total
  } catch {
    // fetchList is called from onMounted; failures are non-fatal here —
    // loading is reset in finally, and store/UI stays empty. The Vitest
    // unhandled-rejection guard requires a catch even when the caller
    // doesn't await the promise.
  } finally {
    loading.value = false
  }
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function eventView(event: string) {
  return EVENT_TYPE_LABELS[event] ?? { label: event, type: 'info' as const }
}

const eventOptions = Object.entries(EVENT_TYPE_LABELS).map(([value, v]) => ({
  value,
  label: v.label,
}))

onMounted(fetchList)
</script>

<template>
  <div class="audit-log">
    <header class="al-header">
      <h2>审计日志</h2>
      <div class="al-actions">
        <el-input
          v-model="filters.actor"
          placeholder="操作人"
          clearable
          style="width: 160px"
        />
        <el-select
          v-model="filters.event"
          placeholder="事件类型"
          clearable
          style="width: 180px"
          filterable
        >
          <el-option
            v-for="opt in eventOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-date-picker
          v-model="filters.from"
          type="datetime"
          placeholder="开始时间"
          format="YYYY-MM-DD HH:mm"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width: 200px"
        />
        <el-date-picker
          v-model="filters.to"
          type="datetime"
          placeholder="结束时间"
          format="YYYY-MM-DD HH:mm"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width: 200px"
        />
        <el-button
          type="primary"
          @click="filters.page = 1; fetchList()"
        >
          查询
        </el-button>
      </div>
    </header>

    <el-table
      v-loading="loading"
      :data="items"
      stripe
      border
    >
      <el-table-column
        label="时间"
        width="180"
      >
        <template #default="{ row }">
          {{ fmtDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column
        label="事件"
        width="130"
      >
        <template #default="{ row }">
          <el-tag
            :type="eventView(row.event).type"
            size="small"
          >
            {{ eventView(row.event).label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="actor"
        label="操作人"
        width="160"
      />
      <el-table-column
        prop="action"
        label="行为"
        width="160"
      />
      <el-table-column
        prop="detail"
        label="详情"
        min-width="280"
        show-overflow-tooltip
      />
      <el-table-column
        prop="ip"
        label="IP"
        width="140"
      />
    </el-table>

    <el-pagination
      v-model:current-page="filters.page"
      v-model:page-size="filters.page_size"
      :total="total"
      layout="total, sizes, prev, pager, next, jumper"
      :page-sizes="[20, 50, 100, 200]"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="fetchList"
      @size-change="fetchList"
    />
  </div>
</template>

<style scoped>
.audit-log { padding: 16px 24px; }
.al-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.al-header h2 { margin: 0; font-size: 18px; }
.al-actions { display: flex; gap: 8px; align-items: center; }
</style>
