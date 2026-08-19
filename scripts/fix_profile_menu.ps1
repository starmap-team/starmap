# Fix ProfileMenu.vue - Add comprehensive validation and improve logout
$content = Get-Content "frontend/src/components/ProfileMenu.vue" -Raw

# Fix 1: Add old_password empty check and new_password > 128 check
$old1 = @'
  if (pwdForm.value.new_password.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (pwdForm.value.new_password !== pwdForm.value.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
'@

$new1 = @'
  if (!pwdForm.value.old_password) {
    ElMessage.warning('请输入原密码')
    return
  }
  if (pwdForm.value.new_password.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (pwdForm.value.new_password.length > 128) {
    ElMessage.warning('新密码不能超过 128 位')
    return
  }
  if (pwdForm.value.new_password !== pwdForm.value.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  if (pwdForm.value.old_password === pwdForm.value.new_password) {
    ElMessage.warning('新密码不能与原密码相同')
    return
  }
  if (/^\d+\$/.test(pwdForm.value.new_password)) {
    ElMessage.warning('新密码不能是纯数字')
    return
  }
'@

$content = $content.Replace($old1, $new1)

# Fix 2: Improve logout error handling (Redis 503 fallback)
$old2 = @'
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
'@

$new2 = @'
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
  try {
    await userStore.logout()
    ElMessage.success('已登出')
  } catch {
    // Redis unavailable: clear local state anyway
    userStore.clearUser()
    ElMessage.success('已登出')
  }
  router.push('/login')
}
'@

$content = $content.Replace($old2, $new2)

Set-Content -Path "frontend/src/components/ProfileMenu.vue" -Value $content -NoNewline -Encoding UTF8
Write-Host "ProfileMenu.vue patched successfully"
