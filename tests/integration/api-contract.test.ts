/**
 * API 联调测试套件
 * 
 * 验证前后端接口的一致性
 * 运行: npx vitest run tests/integration/api-contract.test.ts
 */

import { describe, it, expect, beforeAll } from 'vitest'
import axios from 'axios'

const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000'
const client = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30000,
})

describe('API 契约一致性测试', () => {
  describe('健康检查', () => {
    it('GET /health 应返回 200', async () => {
      const response = await client.get('/health')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('status')
    })
  })

  describe('职位管理', () => {
    it('GET /positions 应返回职位列表', async () => {
      const response = await client.get('/positions')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('items')
      expect(Array.isArray(response.data.items)).toBe(true)
    })

    it('GET /positions/{id} 应返回职位详情', async () => {
      // 先获取列表
      const listResponse = await client.get('/positions')
      const items = listResponse.data.items
      
      if (items.length === 0) {
        console.log('跳过：无职位数据')
        return
      }
      
      const positionId = items[0].position_id || items[0].id
      const response = await client.get(`/positions/${positionId}`)
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('position_id')
      expect(response.data).toHaveProperty('name')
    })
  })

  describe('信息提取', () => {
    it('POST /extract/jd 应返回提取结果', async () => {
      const jdText = '负责后端服务架构设计与开发，精通 Python/Go，熟悉分布式系统...'
      const response = await client.post('/extract/jd', {
        jd_content: jdText,
      })
      
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('position_name')
      expect(response.data).toHaveProperty('required_skills')
      expect(Array.isArray(response.data.required_skills)).toBe(true)
    })
  })

  describe('匹配诊断', () => {
    it('POST /match/position 应返回匹配结果', async () => {
      const response = await client.post('/match/position', {
        person_skills: [
          { name: 'Python', proficiency: '熟练' },
          { name: 'FastAPI', proficiency: '熟悉' },
        ],
        target_position: '后端开发工程师',
      })
      
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('match_score')
      expect(response.data).toHaveProperty('matched_skills')
      expect(response.data).toHaveProperty('gap_skills')
    })

    it('GET /match/history 应返回历史记录', async () => {
      const response = await client.get('/match/history')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('items')
      expect(Array.isArray(response.data.items)).toBe(true)
    })
  })

  describe('图谱查询', () => {
    it('GET /graph/overview 应返回领域概览', async () => {
      const response = await client.get('/graph/overview')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('domains')
      expect(response.data).toHaveProperty('connections')
    })

    it('GET /graph/position/{id}/skills 应返回职位技能', async () => {
      // 先获取职位列表
      const listResponse = await client.get('/positions')
      const items = listResponse.data.items
      
      if (items.length === 0) {
        console.log('跳过：无职位数据')
        return
      }
      
      const positionId = items[0].position_id || items[0].id
      const response = await client.get(`/graph/position/${positionId}/skills`)
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('position')
      expect(response.data).toHaveProperty('skills')
    })
  })

  describe('演化分析', () => {
    it('GET /evolution/trends 应返回趋势数据', async () => {
      const response = await client.get('/evolution/trends')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('items')
    })

    it('GET /evolution/paths/all 应返回演化路径', async () => {
      const response = await client.get('/evolution/paths/all')
      expect(response.status).toBe(200)
      expect(Array.isArray(response.data)).toBe(true)
    })
  })

  describe('质量监控', () => {
    it('GET /quality/dashboard 应返回质量仪表板', async () => {
      const response = await client.get('/quality/dashboard')
      expect(response.status).toBe(200)
      expect(response.data).toHaveProperty('report')
    })
  })
})
