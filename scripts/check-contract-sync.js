/**
 * API 契约同步检查脚本
 * 
 * 用于 CI/CD 中验证前后端代码与 OpenAPI 契约的一致性
 * 运行: node scripts/check-contract-sync.js
 */

const { execSync } = require('child_process')
const { readFileSync, existsSync } = require('fs')
const { resolve } = require('path')

// 颜色输出
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
}

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`)
}

// 检查文件编码
function checkFileEncoding(filePath) {
  try {
    const content = readFileSync(filePath)
    // 检查是否包含 UTF-8 BOM
    if (content[0] === 0xEF && content[1] === 0xBB && content[2] === 0xBF) {
      return { valid: true, bom: true }
    }
    // 检查是否包含乱码（简单检查）
    const text = content.toString('utf-8')
    const hasGarbled = /[\uFFFD\u0000-\u001F]/.test(text)
    return { valid: !hasGarbled, bom: false }
  } catch (error) {
    return { valid: false, error: error.message }
  }
}

// 检查后端文件编码
function checkBackendEncoding() {
  log('\n🔍 检查后端文件编码...', 'blue')
  
  const files = [
    'backend/app/api/v1/router.py',
    'backend/app/api/v1/match.py',
    'backend/app/api/v1/extract.py',
    'backend/app/api/v1/graph.py',
    'backend/app/api/v1/evolution.py',
  ]
  
  let hasError = false
  
  for (const file of files) {
    const filePath = resolve(__dirname, '..', file)
    if (!existsSync(filePath)) {
      log(`  ❌ ${file} - 文件不存在`, 'red')
      hasError = true
      continue
    }
    
    const result = checkFileEncoding(filePath)
    if (!result.valid) {
      log(`  ❌ ${file} - 编码异常或包含乱码`, 'red')
      hasError = true
    } else {
      log(`  ✅ ${file} - 编码正常`, 'green')
    }
  }
  
  return !hasError
}

// 检查前端类型同步
function checkFrontendTypes() {
  log('\n🔍 检查前端类型同步...', 'blue')
  
  const schemaPath = resolve(__dirname, '../frontend/src/api/schema.ts')
  const openApiPath = resolve(__dirname, '../starmap-contracts/openapi.yaml')
  
  if (!existsSync(schemaPath)) {
    log('  ❌ frontend/src/api/schema.ts 不存在', 'red')
    return false
  }
  
  if (!existsSync(openApiPath)) {
    log('  ❌ starmap-contracts/openapi.yaml 不存在', 'red')
    return false
  }
  
  const schemaStat = require('fs').statSync(schemaPath)
  const openApiStat = require('fs').statSync(openApiPath)
  
  if (schemaStat.mtime < openApiStat.mtime) {
    log('  ⚠️  schema.ts 可能比 openapi.yaml 旧', 'yellow')
    log('     建议运行: cd frontend && npm run gen:api', 'yellow')
    return false
  }
  
  log('  ✅ 前端类型已同步', 'green')
  return true
}

// 检查 API 路径一致性
function checkApiPathConsistency() {
  log('\n🔍 检查 API 路径一致性...', 'blue')
  
  // 检查 Vite 代理配置
  const viteConfigPath = resolve(__dirname, '../frontend/vite.config.ts')
  if (existsSync(viteConfigPath)) {
    const content = readFileSync(viteConfigPath, 'utf-8')
    if (content.includes("proxy: {\n      '/api': {")) {
      log('  ⚠️  Vite 代理配置可能不正确', 'yellow')
      log("     建议将 proxy: { '/api': {...} } 改为 proxy: { '/api/v1': {...} }", 'yellow')
      return false
    }
    if (content.includes("proxy: {\n      '/api/v1': {")) {
      log('  ✅ Vite 代理配置正确', 'green')
      return true
    }
  }
  
  log('  ⚠️  无法验证 Vite 代理配置', 'yellow')
  return true
}

// 检查错误处理一致性
function checkErrorHandling() {
  log('\n🔍 检查错误处理一致性...', 'blue')
  
  const requestPath = resolve(__dirname, '../frontend/src/api/request.ts')
  if (!existsSync(requestPath)) {
    log('  ⚠️  无法找到 request.ts', 'yellow')
    return true
  }
  
  const content = readFileSync(requestPath, 'utf-8')
  
  if (content.includes('detail') && content.includes('error.response?.data')) {
    log('  ✅ 错误处理已使用后端 detail 字段', 'green')
    return true
  } else {
    log('  ⚠️  错误处理可能未使用后端 detail 字段', 'yellow')
    log('     建议在错误处理中添加: const detail = (error.response?.data as any)?.detail', 'yellow')
    return false
  }
}

// 主函数
function main() {
  log('🚀 StarMap API 契约同步检查', 'blue')
  log('=' .repeat(50), 'blue')
  
  const results = {
    encoding: checkBackendEncoding(),
    types: checkFrontendTypes(),
    paths: checkApiPathConsistency(),
    errors: checkErrorHandling(),
  }
  
  log('\n' + '='.repeat(50), 'blue')
  log('📊 检查结果:', 'blue')
  
  const total = Object.keys(results).length
  const passed = Object.values(results).filter(Boolean).length
  
  log(`\n✅ 通过: ${passed}/${total}`, 'green')
  
  if (passed < total) {
    log(`❌ 失败: ${total - passed}/${total}`, 'red')
    log('\n请修复上述问题后再提交代码。', 'yellow')
    process.exit(1)
  } else {
    log('\n🎉 所有检查通过！', 'green')
    process.exit(0)
  }
}

main()
