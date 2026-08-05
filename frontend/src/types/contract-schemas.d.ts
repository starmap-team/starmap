/**
 * 契约 JSON Schema 导入声明（PLAN-014）。
 *
 * schema 文件由 scripts/export_json_schemas.py 从后端 Pydantic 生成，
 * 位于仓库根 starmap-contracts/schemas/（frontend 目录外）。
 * 运行时由 Vite 直接以 JSON 解析；此处声明类型供 vue-tsc 使用。
 */
declare module '../../starmap-contracts/schemas/*.schema.json' {
  import type { JSONSchema } from '@/validation/types'

  const schema: JSONSchema
  export default schema
}
