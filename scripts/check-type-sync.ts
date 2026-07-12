/**
 * API 类型定义同步检查
 * 
 * 验证前端 stores 中的类型定义与 OpenAPI 契约的一致性
 * 运行: npx tsx scripts/check-type-sync.ts
 */

import { readFileSync, existsSync } from 'fs'
import { resolve } from 'path'

// 颜色输出
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
}

function log(message: string, color: keyof typeof colors = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`)
}

// 检查接口字段一致性
interface FieldCheck {
  name: string
  required: boolean
  type: string
}

interface TypeCheckResult {
  name: string
  contractFields: FieldCheck[]
  frontendFields: FieldCheck[]
  missingFields: string[]
  extraFields: string[]
}

// 从 OpenAPI 契约中提取字段
function extractContractFields(schemaName: string): FieldCheck[] {
  const openApiPath = resolve(__dirname, '../starmap-contracts/openapi.yaml')
  if (!existsSync(openApiPath)) {
    log(`❌ 找不到 OpenAPI 契约文件: ${openApiPath}`, 'red')
    return []
  }

  const content = readFileSync(openApiPath, 'utf-8')
  
  // 简单解析 YAML 中的 schema 定义
  const schemaRegex = new RegExp(`    ${schemaName}:\\s*\\n      type: object[\\s\\S]*?(?=    [A-Z]|$)`)
  const match = content.match(schemaRegex)
  
  if (!match) {
    log(`⚠️  契约中未找到 schema: ${schemaName}`, 'yellow')
    return []
  }
  
  const fields: FieldCheck[] = []
  const fieldRegex = /        ([a-z_]+):\s*\n\s*type:\s*(\w+)/g
  let fieldMatch
  
  while ((fieldMatch = fieldRegex.exec(match[0])) !== null) {
    fields.push({
      name: fieldMatch[1],
      required: match[0].includes(`required: [${fieldMatch[1]}`) || 
                match[0].includes(`required: [${fieldMatch[1]}`) ||
                match[0].includes(`required:\\s*\\n\\s*-\\s*${fieldMatch[1]}`),
      type: fieldMatch[2],
    })
  }
  
  return fields
}

// 从前端 store 中提取字段
function extractFrontendFields(filePath: string, interfaceName: string): FieldCheck[] {
  if (!existsSync(filePath)) {
    log(`❌ 找不到前端文件: ${filePath}`, 'red')
    return []
  }

  const content = readFileSync(filePath, 'utf-8')
  
  // 查找接口定义
  const interfaceRegex = new RegExp(`export interface ${interfaceName} \\{([\\s\\S]*?)\\}`)
  const match = content.match(interfaceRegex)
  
  if (!match) {
    log(`⚠️  前端文件中未找到接口: ${interfaceName}`, 'yellow')
    return []
  }
  
  const fields: FieldCheck[] = []
  const fieldRegex = /\s+([a-z_]+)\??:\s*(\w+)/g
  let fieldMatch
  
  while ((fieldMatch = fieldRegex.exec(match[1])) !== null) {
    fields.push({
      name: fieldMatch[1],
      required: !fieldMatch[0].includes('?'),
      type: fieldMatch[2],
    })
  }
  
  return fields
}

// 检查类型一致性
function checkTypeConsistency(schemaName: string, filePath: string, interfaceName: string): TypeCheckResult {
  const contractFields = extractContractFields(schemaName)
  const frontendFields = extractFrontendFields(filePath, interfaceName)
  
  const contractFieldNames = new Set(contractFields.map(f => f.name))
  const frontendFieldNames = new Set(frontendFields.map(f => f.name))
  
  const missingFields = [...contractFieldNames].filter(f => !frontendFieldNames.has(f))
  const extraFields = [...frontendFieldNames].filter(f => !contractFieldNames.has(f))
  
  return {
    name: schemaName,
    contractFields,
    frontendFields,
    missingFields,
    extraFields,
  }
}

// 主函数
function main() {
  log('🔍 StarMap API 类型同步检查', 'blue')
  log('=' .repeat(50), 'blue')
  
  const checks = [
    {
      schema: 'MatchResult',
      file: 'frontend/src/stores/match.ts',
      interface: 'MatchResult',
    },
    {
      schema: 'ExtractionResult',
      file: 'frontend/src/stores/jd.ts',
      interface: 'JDExtractResult',
    },
    {
      schema: 'DomainOverviewResponse',
      file: 'frontend/src/stores/graph.ts',
      interface: 'DomainOverviewItem',
    },
  ]
  
  let hasError = false
  
  for (const check of checks) {
    log(`\n📋 检查: ${check.schema}`, 'blue')
    
    const result = checkTypeConsistency(check.schema, check.file, check.interface)
    
    log(`  契约字段: ${result.contractFields.length} 个`, 'green')
    log(`  前端字段: ${result.frontendFields.length} 个`, 'green')
    
    if (result.missingFields.length > 0) {
      log(`  ❌ 缺失字段: ${result.missingFields.join(', ')}`, 'red')
      hasError = true
    }
    
    if (result.extraFields.length > 0) {
      log(`  ⚠️  额外字段: ${result.extraFields.join(', ')}`, 'yellow')
    }
    
    if (result.missingFields.length === 0 && result.extraFields.length === 0) {
      log(`  ✅ 完全一致`, 'green')
    }
  }
  
  log('\n' + '='.repeat(50), 'blue')
  
  if (hasError) {
    log('❌ 类型同步检查未通过', 'red')
    log('请同步更新契约和前端类型', 'yellow')
    process.exit(1)
  } else {
    log('✅ 类型同步检查通过', 'green')
    process.exit(0)
  }
}

main()
