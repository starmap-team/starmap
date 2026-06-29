import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useGraphStore, type GraphNode } from '../graph'

describe('useGraphStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should have correct initial state', () => {
    const store = useGraphStore()
    expect(store.allNodes).toEqual([])
    expect(store.allEdges).toEqual([])
    expect(store.currentLayer).toBe('domain')
    expect(store.loading).toBe(false)
    expect(store.expandedKAId).toBeNull()
    expect(store.expandedPositionId).toBeNull()
  })

  it('should start with empty domains', () => {
    const store = useGraphStore()
    expect(store.domains).toEqual([])
    expect(store.domainConnections).toEqual([])
  })

  it('should compute nodeMap from allNodes', () => {
    const store = useGraphStore()
    store.allNodes = [
      { id: '1', labels: ['Position'], properties: { name: 'Dev' } },
      { id: '2', labels: ['Skill'], properties: { name: 'Python' } },
    ] as GraphNode[]

    expect(store.nodeMap.size).toBe(2)
    expect(store.nodeMap.get('1')?.properties.name).toBe('Dev')
    expect(store.nodeMap.get('2')?.properties.name).toBe('Python')
  })

  it('should return domain visible nodes from domains list', () => {
    const store = useGraphStore()
    store.currentLayer = 'domain'
    store.domains = [
      { id: 'ka1', name: 'AI', position_count: 10, skill_count: 50, color: '#9B59B6' },
      { id: 'ka2', name: '前端', position_count: 8, skill_count: 30, color: '#409EFF' },
    ]

    expect(store.visibleNodes).toHaveLength(2)
    expect(store.visibleNodes[0].id).toBe('ka1')
    expect(store.visibleNodes[0].labels).toContain('KnowledgeArea')
  })

  it('should navigate layers correctly', () => {
    const store = useGraphStore()
    store.currentLayer = 'position'
    store.expandedKAId = 'ka1'
    store.expandedKAName = 'AI'
    store.expandedPositionId = 'pos1'

    store.goToDomainLayer()
    expect(store.currentLayer).toBe('domain')
    expect(store.expandedKAId).toBeNull()
    expect(store.expandedPositionId).toBeNull()
  })

  it('should set loading state', () => {
    const store = useGraphStore()
    store.loading = true
    expect(store.loading).toBe(true)
  })
})
