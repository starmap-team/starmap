<script setup lang="ts">
/**
 * ChangePassword — dedicated forced password-change page.
 *
 * Rendered at /change-password. Two modes:
 * 1. forced=1 query param or userStore.mustChangePassword=true → full-page
 * forced mode: cancel button hidden, cannot navigate away.
 * 2. Normal mode → simple standalone form with cancel back to /.
 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import request from '@/api/request'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// ── Mode detection ──
const forced = computed(
  () => route.query.forced === '1' || userStore.mustChangePassword,
)

const form = ref({ old_password: '', new_password: '', confirm_password: '' })
const submitting = ref(false)

// ── Frontend validation ──
function validate(): string | null {
  if (!form.value.old_password)
    return '请输入原密码'
  if (form.value.new_password.length < 8)
    return '新密码至少 8 位'
  if (form.value.new_password.length > 128)
    return '新密码不能超过 128 位'
  if (form.value.new_password !== form.value.confirm_password)
    return '两次输入的新密码不一致'
  if (form.value.old_password === form.value.new_password)
    return '新密码不能与原密码相同'
  if (/^\d+$/.test(form.value.new_password))
    return '新密码不能是纯数字'
 // ponytail: basic check — backend enforces stronger rules
  return null
}

// ── Submit ──
async function submit() {
  const err = validate()
  if (err) { ElMessage.warning(err); return }

  submitting.value = true
  try {
    await request.post('/auth/change-password', {
      old_password: form.value.old_password,
      new_password: form.value.new_password,
    })

 // Verify server state
    try {
      const me = await request.get('/auth/me') as {
        must_change_password: boolean
      }
      if (userStore.user) {
        userStore.setUser({
          ...userStore.user,
          must_change_password: me.must_change_password,
        })
      }
    } catch {
 // ponytail: /auth/me best-effort, fall back to local flag
      if (userStore.user) {
        userStore.setUser({ ...userStore.user, must_change_password: false })
      }
    }

    ElMessage.success('密码修改成功')
    form.value = { old_password: '', new_password: '', confirm_password: '' }

 // Redirect back or home
    const target = (route.query.redirect as string) || '/'
    router.push(target)
  } catch (e: unknown) {
    const err = e as { response?: { status?: number; data?: { detail?: string } } }
    const status = err?.response?.status
    if (status === 400) {
      ElMessage.error(err?.response?.data?.detail || '原密码错误')
    } else if (status === 422) {
      ElMessage.error(err?.response?.data?.detail || '新密码不符合安全要求')
    } else {
      ElMessage.error('密码修改失败，请稍后重试')
    }
  } finally {
    submitting.value = false
  }
}

function goBack() {
  router.push('/')
}

// ponytail: race-condition guard moved into router beforeEach (see
// router/index.ts). Leaving this hook empty avoids the empty-paint flash the
// QA harness reported when localStorage was cleared mid-session.
onMounted(() => { /* no-op */ })
</script>

<template>
  <div class="change-pwd-page">
    <div class="pwd-card">
      <div class="pwd-header">
        <el-icon
          class="pwd-icon"
          :size="28"
        >
          <Lock />
        </el-icon>
        <h2>{{ forced ? '首次登录，请修改密码' : '修改密码' }}</h2>
      </div>

      <div
        v-if="forced"
        class="pwd-banner"
      >
        管理员要求您首次登录后修改密码，完成后才能继续使用系统。
      </div>

      <el-form
        label-width="80px"
        :disabled="submitting"
        @submit.prevent
      >
        <el-form-item
          label="原密码"
          required
        >
          <el-input
            v-model="form.old_password"
            type="password"
            show-password
            placeholder="输入当前密码"
            autocomplete="current-password"
          />
        </el-form-item>

        <el-form-item
          label="新密码"
          required
        >
          <el-input
            v-model="form.new_password"
            type="password"
            show-password
            placeholder="至少 8 位，不能与原密码相同"
            autocomplete="new-password"
          />
        </el-form-item>

        <el-form-item
          label="确认密码"
          required
        >
          <el-input
            v-model="form.confirm_password"
            type="password"
            show-password
            placeholder="再次输入新密码"
            autocomplete="new-password"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="submitting"
            style="width: 100%"
            @click="submit"
          >
            确认修改
          </el-button>
        </el-form-item>

        <el-form-item v-if="!forced">
          <el-button
            style="width: 100%"
            @click="goBack"
          >
            返回首页
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.change-pwd-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--el-bg-color-page);
  padding: 24px;
}

.pwd-card {
  width: 100%;
  max-width: 420px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 32px 28px 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.pwd-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.pwd-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.pwd-icon {
  color: var(--el-color-primary);
}

.pwd-banner {
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning-dark-2);
  border: 1px solid var(--el-color-warning-light-6);
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 20px;
  font-size: 13px;
  line-height: 1.6;
}
</style>
