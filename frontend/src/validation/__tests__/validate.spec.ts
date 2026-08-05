/**
 * validate.ts / useResponseValidation.ts — $ref 解析与响应校验测试
 *
 * 覆盖: $ref 嵌套递归校验 / 悬空 $ref 容错 / definitionPath 解析 /
 *       validateResponse 失败不阻断（返回原数据）
 * Fixture 镜像 scripts/export_json_schemas.py 的实际输出结构：
 * 根文档含 definitions + $defs，refs 指向 "#/$defs/X"。
 */
import { describe, it, expect } from 'vitest'
import type { JSONSchema } from '../types'
import { validate } from '../validate'
import { useResponseValidation } from '../useResponseValidation'

/** 与生成 schema 同构的 fixture（含 $defs 提升 + $ref 链） */
const doc: JSONSchema = {
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  definitions: {
    SkillNode: {
      type: 'object',
      properties: {
        skill_id: { type: 'string', minLength: 1 },
        name: { type: 'string' },
        confidence: { type: 'number', minimum: 0, maximum: 1 },
      },
      required: ['skill_id', 'name'],
    },
    PositionNode: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        skills_required: {
          type: 'array',
          items: { $ref: '#/$defs/SkillNode' },
        },
      },
      required: ['name'],
    },
    PositionListResponse: {
      type: 'object',
      properties: {
        items: { type: 'array', items: { $ref: '#/$defs/PositionNode' } },
        total: { type: 'integer', minimum: 0 },
        page: { type: 'integer', minimum: 1 },
      },
      required: ['items', 'total', 'page'],
    },
  },
  $defs: {
    SkillNode: {
      type: 'object',
      properties: {
        skill_id: { type: 'string', minLength: 1 },
        name: { type: 'string' },
        confidence: { type: 'number', minimum: 0, maximum: 1 },
      },
      required: ['skill_id', 'name'],
    },
    PositionNode: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        skills_required: {
          type: 'array',
          items: { $ref: '#/$defs/SkillNode' },
        },
      },
      required: ['name'],
    },
  },
}

const listSchema = doc.definitions!.PositionListResponse

describe('validate() $ref 解析', () => {
  it('通过 $ref 链递归校验嵌套结构（合法数据通过）', () => {
    const data = {
      items: [
        { name: '后端工程师', skills_required: [{ skill_id: 'py-1', name: 'Python' }] },
      ],
      total: 1,
      page: 1,
    }
    expect(validate(data, listSchema, doc).valid).toBe(true)
  })

  it('通过 $ref 链捕获深层必填缺失（错误路径带索引）', () => {
    const data = {
      items: [{ name: '后端工程师', skills_required: [{ name: 'Python' }] }],
      total: 1,
      page: 1,
    }
    const result = validate(data, listSchema, doc)
    expect(result.valid).toBe(false)
    expect(result.errors.some(e => e.field === 'items[0].skills_required[0].skill_id')).toBe(true)
  })

  it('校验数组元素 $ref 的类型约束（confidence 超界）', () => {
    const data = {
      items: [{ name: '后端', skills_required: [{ skill_id: 's', name: 'Py', confidence: 5 }] }],
      total: 1,
      page: 1,
    }
    expect(validate(data, listSchema, doc).valid).toBe(false)
  })

  it('悬空 $ref 静默跳过（不抛异常，视为通过）', () => {
    const broken: JSONSchema = {
      ...doc,
      definitions: {
        Wrapper: {
          type: 'object',
          properties: { inner: { $ref: '#/$defs/NotExists' } },
          required: ['inner'],
        },
      },
    }
    expect(validate({ inner: 42 }, broken.definitions!.Wrapper, broken).valid).toBe(true)
  })
})

describe('useResponseValidation() definitionPath 解析', () => {
  it('按 definitionPath 校验并对不匹配输出警告但返回原数据（不阻断）', () => {
    const { validateResponse } = useResponseValidation()
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const groupSpy = vi.spyOn(console, 'groupCollapsed').mockImplementation(() => {})
    const raw = { items: [], total: 'oops', page: 0 }
    const ret = validateResponse(raw, doc, '/positions', 'PositionListResponse')
    expect(ret).toBe(raw)
    expect(warnSpy).toHaveBeenCalled()
    warnSpy.mockRestore()
    groupSpy.mockRestore()
  })

  it('definitionPath 不存在时降级返回原数据（不抛异常）', () => {
    const { validateResponse } = useResponseValidation()
    const raw = { anything: true }
    expect(validateResponse(raw, doc, '/x', 'NotADefinition')).toBe(raw)
  })

  it('不带 definitionPath 时直接校验传入 schema', () => {
    const { validateResponse } = useResponseValidation()
    const raw = { items: [], total: 0, page: 1 }
    expect(validateResponse(raw, listSchema, '/positions')).toBe(raw)
  })
})
