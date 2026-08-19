<script setup lang="ts">
/**
 * ProfileMenu 鈥?top-right user dropdown in MainLayout.
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
  400: '鍘熷瘑鐮侀敊璇?,
  401: '鐧诲綍宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?,
  422: '鏂板瘑鐮佷笉绗﹀悎瑕佹眰',
}

async function submitChangePassword() {
  if (pwdForm.value.new_password.length < 8) {
    ElMessage.warning('鏂板瘑鐮佽嚦灏?8 浣?)
    return
  }
  if (pwdForm.value.new_password !== pwdForm.value.confirm_password) {
    ElMessage.warning('涓ゆ杈撳叆鐨勬柊瀵嗙爜涓嶄竴鑷?)
    return
  }
  try {
    await request.post('/auth/change-password', {
      old_password: pwdForm.value.old_password,
      new_password: pwdForm.value.new_password,
    })
    ElMessage.success('瀵嗙爜淇敼鎴愬姛')
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
    ElMessage.error(detail || errorMessages[status ?? 0] || '瀵嗙爜淇敼澶辫触')
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('纭鐧诲嚭锛?, '鐧诲嚭', {
      type: 'warning',
      confirmButtonText: '纭',
      cancelButtonText: '鍙栨秷',
    })
  } catch {
    return
  }
  await userStore.logout()
  ElMessage.success('宸茬櫥鍑?)
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
        {{ userStore.user?.username ?? '鏈櫥褰? }}
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
          <el-icon><Lock /></el-icon> 蹇呴』鍏堜慨鏀瑰瘑鐮?        </el-dropdown-item>
        <el-dropdown-item command="change-password">
          <el-icon><Lock /></el-icon> 淇敼瀵嗙爜
        </el-dropdown-item>
        <el-dropdown-item
          command="logout"
          divided
        >
          <el-icon><SwitchButton /></el-icon> 閫€鍑虹櫥褰?        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>

  <el-dialog
    v-model="showChangePwd"
    title="淇敼瀵嗙爜"
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
      鈿狅笍 绠＄悊鍛樿姹傛偍棣栨鐧诲綍鍚庝慨鏀瑰瘑鐮佸悗鎵嶈兘缁х画浣跨敤绯荤粺銆?    </p>
    <el-form label-width="100px">
      <el-form-item
        label="鍘熷瘑鐮?
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
        label="鏂板瘑鐮?
        required
      >
        <el-input
          v-model="pwdForm.new_password"
          type="password"
          show-password
          placeholder="鑷冲皯 8 浣?
          autocomplete="new-password"
        />
      </el-form-item>
      <el-form-item
        label="纭瀵嗙爜"
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
        鍙栨秷
      </el-button>
      <el-button
        type="primary"
        @click="submitChangePassword"
      >
        鎻愪氦
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
