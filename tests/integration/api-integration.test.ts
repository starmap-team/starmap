/**
 * StarMap API 联调测试报告
 * 
 * 运行: npx vitest run tests/integration/api-integration.test.ts
 */

import { describe, it, expect, beforeAll } from 'vitest'
import axios from 'axios'

const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000'
const client = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30000,
})

describe('StarMap API 联调测试', () => {
  describe('模块 1: 系统健康', () => {
    it('GET /health 应返回健康状态', async () => {
      const response = await client.get('/health')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('status')
      expect(response.data.status).toBe('ok')
    })
  })

  describe('模块 2: 职位管理', () => {
    it('GET /positions 应返回职位列表', async () => {
      const response = await client.get('/positions')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('items')
      expect(Array.isArray(response.data.items)).toBe(true)
      expect(response.data).toHaveProperty('total')
      expect(response.data).toHaveProperty('page')
      expect(response.data).toHaveProperty('page_size')
    })

    it('GET /positions 应支持分页', async () => {
      const response = await client.get('/positions', {
        params: { page: 1, page_size: 5 }
      })
      expect(response.status).toBe(200)
      expect(response.data.items.length).toBeLessThanOrEqual(5)
    })

    it('GET /positions 应支持搜索', async () => {
      const response = await client.get('/positions', {
        params: { search: '工程师' }
      })
      expect(response.status).toBe(200)
      expect(Array.isArray(response.data.items)).toBe(true)
    })
  })

  describe('模块 3: 信息提取', () => {
    it('POST /extract/jd 应返回提取结果', async () => {
      const jdText = '负责后端服务架构设计与开发，精通 Python/Go，熟悉分布式系统，3年以上经验。'
      const response = await client.post('/extract/jd', {
        jd_content: jdText,
      })
      
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('position_name')
      expect(response.data).toHaveProperty('required_skills')
      expect(Array.isArray(response.data.required_skills)).toBe(true)
    })

    it('POST /extract/jd 空内容应返回 422', async () => {
      try {
        await client.post('/extract/jd', {
          jd_content: '',
        })
        expect(false).toBe(true) // 不应到达这里
      } catch (error: any) {
        expect(error.response.status).toBe(422)
      }
    })
  })

  describe('模块 4: 匹配诊断', () => {
    it('POST /match/position 应返回匹配结果', async () => {
      const response = await client.post('/match/position', {
        person_skills: [
          { name: 'Python', proficiency: '熟练' },
          { name: 'FastAPI', proficiency: '熟悉' },
          { name: 'PostgreSQL', proficiency: '熟悉' },
        ],
        target_position: '后端开发工程师',
      })
      
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('match_score')
      expect(response.data.match_score).toBeGreaterThanOrEqual(0)
      expect(response.data.match_score).toBeLessThanOrEqual(1)
      expect(response.data).toHaveProperty('matched_skills')
      expect(response.data).toHaveProperty('gap_skills')
      expect(Array.isArray(response.data.matched_skills)).toBe(true)
      expect(Array.isArray(response.data.gap_skills)).toBe(true)
    })

    it('POST /match/position 空技能应返回 400', async () => {
      try {
        await client.post('/match/position', {
          person_skills: [],
          target_position: '后端开发工程师',
        })
        expect(false).toBe(true)
      } catch (error: any) {
        expect(error.response.status).toBe(400)
      }
    })

    it('GET /match/history 应返回历史记录', async () => {
      const response = await client.get('/match/history')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('items')
      expect(Array.isArray(response.data.items)).toBe(true)
    })
  })

  describe('模块 5: 图谱查询', () => {
    it('GET /graph/overview 应返回领域概览', async () => {
      const response = await client.get('/graph/overview')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('domains')
      expect(response.data).toHaveProperty('connections')
      expect(Array.isArray(response.data.domains)).toBe(true)
      expect(Array.isArray(response.data.connections)).toBe(true)
    })

    it('GET /graph/overview 应支持分组', async () => {
      const response = await client.get('/graph/overview', {
        params: { group_by: 'tech_stack' }
      })
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('domains')
    })
  })

  describe('模块 6: 演化分析', () => {
    it('GET /evolution/trends 应返回趋势数据', async () => {
      const response = await client.get('/evolution/trends')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('items')
      expect(Array.isArray(response.data.items)).toBe(true)
    })

    it('GET /evolution/paths/all 应返回演化路径', async () => {
      const response = await client.get('/evolution/paths/all')
      expect(response.status).toBe(200)
      expect(Array.isArray(response.data)).toBe(true)
    })

    it('GET /evolution/emerging-skills 应返回新兴技能', async () => {
      const response = await client.get('/evolution/emerging-skills')
      expect(response.status).toBe(200)
      expect(Array.isArray(response.data)).toBe(true)
    })
  })

  describe('模块 7: 质量监控', () => {
    it('GET /quality/dashboard 应返回质量仪表板', async () => {
      const response = await client.get('/quality/dashboard')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('report')
    })

    it('GET /quality/trends 应返回质量趋势', async () => {
      const response = await client.get('/quality/trends', {
        params: { period: '7d' }
      })
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('period')
      expect(response.data).toHaveProperty('data_points')
    })
  })

  describe('模块 8: 数据大屏', () => {
    it('GET /dashboard/overview 应返回概览数据', async () => {
      const response = await client.get('/dashboard/overview')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('total_nodes')
      expect(response.data).toHaveProperty('total_edges')
      expect(response.data).toHaveProperty('total_positions')
      expect(response.data).toHaveProperty('total_skills')
    })

    it('GET /dashboard/trends 应返回趋势数据', async () => {
      const response = await client.get('/dashboard/trends')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('period')
      expect(response.data).toHaveProperty('data_points')
    })
  })

  describe('模块 9: 学习中心', () => {
    it('GET /learning/plans 应返回学习计划', async () => {
      const response = await client.get('/learning/plans')
      expect(response.status).toBe(200)
      expect(Array.isArray(response.data)).toBe(true)
    })

    it('POST /learning/plan 应创建学习计划', async () => {
      const response = await client.post('/learning/plan', {
        position: '后端开发工程师',
        skills: [
          { skill: 'Python', importance: 'required', gap_level: '完全缺失' },
        ],
      })
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('plan_id')
      expect(response.data).toHaveProperty('position')
    })
  })

  describe('模块 10: 流水线', () => {
    it('GET /pipeline/status 应返回流水线状态', async () => {
      const response = await client.get('/pipeline/status')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('is_running')
    })

    it('GET /pipeline/stages 应返回阶段状态', async () => {
      const response = await client.get('/pipeline/stages')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('stages')
      expect(Array.isArray(response.data.stages)).toBe(true)
    })
  })
})
