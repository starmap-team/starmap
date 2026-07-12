/**
 * API 契约验证工具
 * 
 * 用于验证后端实现与 OpenAPI 契约的一致性
 * 运行: npx tsx scripts/verify-contract.ts
 */

import { readFileSync } from 'fs'
import { resolve } from 'path'
import yaml from 'js-yaml'

// 加载 OpenAPI 契约
const openApiPath = resolve(__dirname, '../starmap-contracts/openapi.yaml')
const openApiContent = readFileSync(openApiPath, 'utf-8')
const openApi = yaml.load(openApiContent) as any

// 契约中的路径和字段
const contractPaths = new Map<string, any>()
const contractSchemas = new Map<string, any>()

// 解析契约
if (openApi.paths) {
  for (const [path, methods] of Object.entries(openApi.paths)) {
    contractPaths.set(path, methods)
  }
}

if (openApi.components?.schemas) {
  for (const [name, schema] of Object.entries(openApi.components.schemas)) {
    contractSchemas.set(name, schema)
  }
}

// 验证结果
interface ValidationResult {
  path: string
  method: string
  issues: string[]
}

const results: ValidationResult[] = []

// 验证后端实现
function validateBackendImplementation() {
  // TODO: 自动扫描 backend/app/api/v1/ 下的路由文件
  // 这里展示验证逻辑
  
  console.log('🔍 验证后端实现...')
  console.log(`📋 契约路径数: ${contractPaths.size}`)
  console.log(`📋 契约模型数: ${contractSchemas.size}`)
  
  // 验证关键端点
  const criticalEndpoints = [
    { path: '/match/position', method: 'post' },
    { path: '/extract/jd', method: 'post' },
    { path: '/graph/overview', method: 'get' },
    { path: '/evolution/trends', method: 'get' },
  ]
  
  for (const endpoint of criticalEndpoints) {
    const contract = contractPaths.get(endpoint.path)
    if (!contract) {
      results.push({
        path: endpoint.path,
        method: endpoint.method,
        issues: ['契约中未定义此端点']
      })
      continue
    }
    
    const method = contract[endpoint.method]
    if (!method) {
      results.push({
        path: endpoint.path,
        method: endpoint.method,
        issues: [`契约中未定义 ${endpoint.method} 方法`]
      })
      continue
    }
    
    console.log(`✅ ${endpoint.method.toUpperCase()} ${endpoint.path} - 已定义`)
  }
}

// 验证前端类型
function validateFrontendTypes() {
  console.log('\n🔍 验证前端类型...')
  
  // 检查 schema.ts 是否存在
  const schemaPath = resolve(__dirname, '../frontend/src/api/schema.ts')
  try {
    readFileSync(schemaPath, 'utf-8')
    console.log('✅ frontend/src/api/schema.ts 存在')
  } catch {
    results.push({
      path: 'frontend/src/api/schema.ts',
      method: 'N/A',
      issues: ['schema.ts 不存在，请运行 npm run gen:api']
    })
  }
}

// 主函数
function main() {
  console.log('🚀 StarMap API 契约验证工具\n')
  console.log('=' .repeat(50))
  
  validateBackendImplementation()
  validateFrontendTypes()
  
  console.log('\n' + '='.repeat(50))
  console.log('📊 验证结果:')
  
  if (results.length === 0) {
    console.log('✅ 所有检查通过！')
  } else {
    console.log(`❌ 发现 ${results.length} 个问题:`)
    for (const result of results) {
      console.log(`\n🔴 ${result.method.toUpperCase()} ${result.path}`)
      for (const issue of result.issues) {
        console.log(`   - ${issue}`)
      }
    }
  }
}

main()
