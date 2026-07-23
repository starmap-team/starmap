<script setup lang="ts">
/**
 * ProfileMenu — top-right user dropdown in MainLayout.
 * Shows the current user, a "change password" dialog, and "logout".
 */
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Lock, SwitchButton } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import request from '@/api/request'

const router = useRouter()
const userStore = useUserStore()
const showChangePwd = ref(false)

const pwdForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const errorMessages: Record<number, string> = {
  400: '原密码错误',
  401: '登录已过期，请重新登录',
  422: '新密码不符合要求',
}

async function submitChangePassword() {
  if (pwdForm.value.new_password.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (pwdForm.value.new_password !== pwdForm.value.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  try {
    await request.post('/auth/change-password', {
      old_password: pwdForm.value.old_password,
      new_password: pwdForm.value.new_password,
    })
    ElMessage.success('密码修改成功')
    showChangePwd.value = false
    pwdForm.value = { old_password: '', new_password: '', confirm_password: '' }
    // Clear must_change_password flag locally
    if (userStore.user) {
      userStore.setUser({ ...userStore.user, must_change_password: false })
    }
  } catch (e: unknown) {
    const err = e as { response?: { status?: number; data?: { detail?: string } } }
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    ElMessage.error(detail || errorMessages[status ?? 0] || '密码修改失败')
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确认登出？', '登出', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await userStore.logout()
  ElMessage.success('已登出')
  router.push('/login')
}

function handleCommand(cmd: string) {
  if (cmd === 'change-password') {
    // Route to dedicated page so the forced=1 flag is picked up
    const forced = userStore.mustChangePassword ? { forced: '1' } : undefined
    router.push({ path: '/change-password', query: forced })
    return
  }
  if (cmd === 'logout') handleLogout()
}

const userInitial = (username?: string | null) => {
  if (!username) return '?'
  return username.slice(0, 1).toUpperCase()
}
</script>

<template>
  <el-dropdown
    trigger="click"
    @command="handleCommand"
  >
    <span class="profile-trigger">
      <span class="avatar">{{ userInitial(userStore.user?.username) }}</span>
      <span class="profile-name">
        {{ userStore.user?.username ?? '未登录' }}
        <el-tag
          v-if="userStore.isAdmin"
          size="small"
          type="danger"
          effect="dark"
          style="margin-left: 4px"
        >admin</el-tag>
      </span>
    </span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item
          v-if="userStore.mustChangePassword"
          command="change-password"
        >
          <el-icon><Lock /></el-icon> 必须先修改密码
        </el-dropdown-item>
        <el-dropdown-item command="change-password">
          <el-icon><Lock /></el-icon> 修改密码
        </el-dropdown-item>
        <el-dropdown-item
          command="logout"
          divided
        >
          <el-icon><SwitchButton /></el-icon> 退出登录
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>

  <el-dialog
    v-model="showChangePwd"
    title="修改密码"
    width="440px"
    :close-on-click-modal="!userStore.mustChangePassword"
    :close-on-press-escape="!userStore.mustChangePassword"
    :show-close="!userStore.mustChangePassword"
    @close="pwdForm = { old_password: '', new_password: '', confirm_password: '' }"
  >
    <p
      v-if="userStore.mustChangePassword"
      class="pwd-hint"
    >
      ⚠️ 管理员要求您首次登录后修改密码后才能继续使用系统。
    </p>
    <el-form label-width="100px">
      <el-form-item
        label="原密码"
        required
      >
        <el-input
          v-model="pwdForm.old_password"
          type="password"
          show-password
          autocomplete="current-password"
        />
      </el-form-item>
      <el-form-item
        label="新密码"
        required
      >
        <el-input
          v-model="pwdForm.new_password"
          type="password"
          show-password
          placeholder="至少 8 位"
          autocomplete="new-password"
        />
      </el-form-item>
      <el-form-item
        label="确认密码"
        required
      >
        <el-input
          v-model="pwdForm.confirm_password"
          type="password"
          show-password
          autocomplete="new-password"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button
        v-if="!userStore.mustChangePassword"
        @click="showChangePwd = false"
      >
        取消
      </el-button>
      <el-button
        type="primary"
        @click="submitChangePassword"
      >
        提交
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.profile-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 20px;
  transition: background-color 0.18s;
}
.profile-trigger:hover {
  background-color: var(--el-fill-color-light);
}
.avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: white;
  font-size: 13px;
  font-weight: 600;
}
.profile-name {
  font-size: 14px;
  color: var(--el-text-color-primary);
}
.pwd-hint {
  color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
  padding: 8px 12px;
  border-radius: 4px;
  margin: 0 0 12px;
  font-size: 13px;
}
</style>
