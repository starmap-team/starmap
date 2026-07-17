<script setup lang="ts">
/**
 * User Management page — admin-only.
 *
 * Uses the new Phase DB-AUTH endpoints:
 *   GET    /admin/users          — paginated list with filters
 *   POST   /admin/users          — create
 *   PATCH  /admin/users/{id}     — role / is_active / must_change_password
 *   DELETE /admin/users/{id}     — soft-delete (disable)
 *   POST   /admin/users/{id}/unlock — clear lockout
 *   POST   /admin/users/{id}/reset-password — admin-set password
 */
import { onMounted, ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'

interface UserRow {
  id: string
  username: string
  email: string | null
  role: string
  is_active: boolean
  must_change_password: boolean
  failed_login_attempts: number
  locked_until: string | null
  last_login_at: string | null
  last_login_ip: string | null
  disabled_at: string | null
  disabled_reason: string | null
  created_at: string | null
}

const loading = ref(false)
const items = ref<UserRow[]>([])
const total = ref(0)

const filters = reactive({
  search: '',
  role: '' as '' | 'admin' | 'user',
  is_active: '' as '' | 'true' | 'false',
  page: 1,
  page_size: 20,
})

const showCreate = ref(false)
const showReset = ref(false)
const resetTarget = ref<UserRow | null>(null)
const resetPassword = ref('')

const createForm = reactive({
  username: '',
  password: '',
  role: 'user' as 'admin' | 'user',
  email: '',
  must_change_password: true,
})

async function fetchList() {
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      page: filters.page,
      page_size: filters.page_size,
    }
    if (filters.search) params.search = filters.search
    if (filters.role) params.role = filters.role
    if (filters.is_active) params.is_active = filters.is_active
    const data = (await request.get('/admin/users', { params })) as {
      total: number
      items: UserRow[]
    }
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function handleToggleActive(u: UserRow) {
  const newVal = !u.is_active
  const action = newVal ? '启用' : '停用'
  try {
    await ElMessageBox.confirm(
      `${action}用户 "${u.username}"？`,
      '确认操作',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await request.patch(`/admin/users/${u.id}`, { is_active: newVal })
    ElMessage.success(`${action}成功`)
    fetchList()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err?.response?.data?.detail ?? `${action}失败`)
  }
}

async function handleChangeRole(u: UserRow, newRole: string) {
  try {
    await request.patch(`/admin/users/${u.id}`, { role: newRole })
    ElMessage.success('角色已更新')
    fetchList()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err?.response?.data?.detail ?? '更新失败')
  }
}

async function handleUnlock(u: UserRow) {
  try {
    await request.post(`/admin/users/${u.id}/unlock`)
    ElMessage.success('账号已解锁')
    fetchList()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err?.response?.data?.detail ?? '解锁失败')
  }
}

function openResetPassword(u: UserRow) {
  resetTarget.value = u
  resetPassword.value = ''
  showReset.value = true
}

async function submitResetPassword() {
  if (!resetTarget.value) return
  if (resetPassword.value.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  try {
    await request.post(`/admin/users/${resetTarget.value.id}/reset-password`, {
      new_password: resetPassword.value,
    })
    ElMessage.success('密码已重置')
    showReset.value = false
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err?.response?.data?.detail ?? '重置失败')
  }
}

function openCreate() {
  Object.assign(createForm, {
    username: '',
    password: '',
    role: 'user',
    email: '',
    must_change_password: true,
  })
  showCreate.value = true
}

async function submitCreate() {
  if (createForm.username.length < 1) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (createForm.password.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  try {
    await request.post('/admin/users', {
      username: createForm.username,
      password: createForm.password,
      role: createForm.role,
      email: createForm.email || undefined,
      must_change_password: createForm.must_change_password,
    })
    ElMessage.success('用户已创建')
    showCreate.value = false
    fetchList()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err?.response?.data?.detail ?? '创建失败')
  }
}

async function handleDelete(u: UserRow) {
  try {
    await ElMessageBox.confirm(
      `确认禁用用户 "${u.username}"？此操作会将账号标记为已停用，可在列表中重新启用。`,
      '确认',
      { type: 'warning' },
    )
  } catch {
    return
  }
  let reason: string | null = null
  try {
    const { value } = await ElMessageBox.prompt('请输入禁用原因（可选）：', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: '',
    })
    reason = value || null
  } catch {
    return // cancelled
  }
  try {
    await request.delete(`/admin/users/${u.id}`, {
      data: { reason: reason ?? undefined },
    })
    ElMessage.success('用户已禁用')
    fetchList()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err?.response?.data?.detail ?? '操作失败')
  }
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

onMounted(fetchList)
</script>

<template>
  <div class="user-management">
    <header class="um-header">
      <h2>用户管理</h2>
      <div class="um-actions">
        <el-input
          v-model="filters.search"
          placeholder="搜索用户名"
          clearable
          style="width: 220px"
          @keyup.enter="filters.page = 1; fetchList()"
          @clear="filters.page = 1; fetchList()"
        />
        <el-select
          v-model="filters.role"
          placeholder="角色"
          clearable
          style="width: 110px"
          @change="filters.page = 1; fetchList()"
        >
          <el-option
            label="全部"
            value=""
          />
          <el-option
            label="admin"
            value="admin"
          />
          <el-option
            label="user"
            value="user"
          />
        </el-select>
        <el-select
          v-model="filters.is_active"
          placeholder="状态"
          clearable
          style="width: 110px"
          @change="filters.page = 1; fetchList()"
        >
          <el-option
            label="全部"
            value=""
          />
          <el-option
            label="启用"
            value="true"
          />
          <el-option
            label="停用"
            value="false"
          />
        </el-select>
        <el-button
          type="primary"
          @click="filters.page = 1; fetchList()"
        >
          查询
        </el-button>
        <el-button
          type="success"
          @click="openCreate"
        >
          + 新建用户
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
        prop="username"
        label="用户名"
        width="160"
      />
      <el-table-column
        prop="role"
        label="角色"
        width="110"
      >
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
            {{ row.role }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="状态"
        width="120"
      >
        <template #default="{ row }">
          <template v-if="row.disabled_at">
            <el-tag type="info">
              已停用
            </el-tag>
          </template>
          <template v-else-if="!row.is_active">
            <el-tag type="warning">
              未激活
            </el-tag>
          </template>
          <template v-else-if="row.locked_until && new Date(row.locked_until) > new Date()">
            <el-tag type="danger">
              已锁定
            </el-tag>
          </template>
          <template v-else>
            <el-tag type="success">
              正常
            </el-tag>
          </template>
        </template>
      </el-table-column>
      <el-table-column
        prop="email"
        label="邮箱"
        width="180"
      />
      <el-table-column
        label="失败次数"
        width="80"
        align="center"
      >
        <template #default="{ row }">
          <span :class="{ 'warn-cell': row.failed_login_attempts >= 3 }">
            {{ row.failed_login_attempts }}
          </span>
        </template>
      </el-table-column>
      <el-table-column
        label="上次登录"
        width="170"
      >
        <template #default="{ row }">
          {{ fmtDate(row.last_login_at) }}
        </template>
      </el-table-column>
      <el-table-column
        label="IP"
        width="120"
      >
        <template #default="{ row }">
          {{ row.last_login_ip || '—' }}
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        min-width="320"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button
            v-if="row.locked_until && new Date(row.locked_until) > new Date()"
            size="small"
            type="warning"
            @click="handleUnlock(row)"
          >
            解锁
          </el-button>
          <el-button
            size="small"
            @click="openResetPassword(row)"
          >
            重置密码
          </el-button>
          <el-select
            :model-value="row.role"
            size="small"
            style="width: 92px; margin-left: 4px"
            @change="(val: string | number) => handleChangeRole(row, String(val))"
          >
            <el-option
              label="admin"
              value="admin"
            />
            <el-option
              label="user"
              value="user"
            />
          </el-select>
          <el-button
            v-if="!row.disabled_at"
            size="small"
            type="danger"
            style="margin-left: 4px"
            @click="handleDelete(row)"
          >
            禁用
          </el-button>
          <el-button
            v-else
            size="small"
            type="success"
            style="margin-left: 4px"
            @click="handleToggleActive(row)"
          >
            重新启用
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="filters.page"
      v-model:page-size="filters.page_size"
      :total="total"
      layout="total, sizes, prev, pager, next, jumper"
      :page-sizes="[10, 20, 50, 100]"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="fetchList"
      @size-change="fetchList"
    />

    <!-- Create dialog -->
    <el-dialog
      v-model="showCreate"
      title="新建用户"
      width="480px"
    >
      <el-form label-width="80px">
        <el-form-item
          label="用户名"
          required
        >
          <el-input
            v-model="createForm.username"
            placeholder="登录用户名"
          />
        </el-form-item>
        <el-form-item
          label="密码"
          required
        >
          <el-input
            v-model="createForm.password"
            type="password"
            placeholder="至少 8 位"
            show-password
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="createForm.role">
            <el-radio value="user">
              user
            </el-radio>
            <el-radio value="admin">
              admin
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input
            v-model="createForm.email"
            placeholder="可选，用于密码找回"
          />
        </el-form-item>
        <el-form-item label="首次登录">
          <el-checkbox v-model="createForm.must_change_password">
            要求用户首次登录后立即修改密码
          </el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="submitCreate"
        >
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- Reset-password dialog -->
    <el-dialog
      v-model="showReset"
      title="重置密码"
      width="420px"
    >
      <p class="um-reset-target">
        用户：<strong>{{ resetTarget?.username }}</strong>
      </p>
      <el-input
        v-model="resetPassword"
        type="password"
        placeholder="新密码（至少 8 位）"
        show-password
      />
      <template #footer>
        <el-button @click="showReset = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="submitResetPassword"
        >
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-management { padding: 16px 24px; }
.um-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.um-header h2 { margin: 0; font-size: 18px; }
.um-actions { display: flex; gap: 8px; align-items: center; }
.warn-cell { color: #e6a23c; font-weight: 600; }
.um-reset-target { margin: 0 0 12px; color: var(--el-text-color-secondary); }
</style>
