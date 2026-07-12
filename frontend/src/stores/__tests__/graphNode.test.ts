import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useGraphNodeStore } from '../graphNode'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('useGraphNodeStore — createGraphNode contract', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('should POST /admin/graph/nodes with type + name + properties', async () => {
    const request = (await import('@/api/request')).default
    // POST returns the created node
    vi.mocked(request.post).mockResolvedValueOnce({
      id: '4:new-1',
      type: 'Skill',
      name: 'Rust',
      properties: { name: 'Rust', category: 'hard_skill' },
      status: 'pending',
    })
    // After create, fetchGraphNodes is called to refresh
    vi.mocked(request.get).mockResolvedValueOnce({
      items: [{ id: '4:new-1', type: 'Skill', name: 'Rust', properties: { name: 'Rust', category: 'hard_skill' }, status: 'pending' }],
    })

    const store = useGraphNodeStore()
    await store.createGraphNode({
      type: 'Skill',
      name: 'Rust',
      properties: { category: 'hard_skill' },
    })

    // Assert the POST payload — this is the contract between frontend and backend
    expect(request.post).toHaveBeenCalledWith('/admin/graph/nodes', {
      type: 'Skill',
      name: 'Rust',
      properties: { category: 'hard_skill' },
    })
  })

  it('should NOT send id field when creating (frontend omits undefined)', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({
      id: '4:new-2',
      type: 'Position',
      name: 'DevOps',
      properties: { name: 'DevOps' },
      status: 'pending',
    })
    vi.mocked(request.get).mockResolvedValueOnce({ items: [] })

    const store = useGraphNodeStore()
    // GraphNodeEditor emits { id: undefined, type, name, properties }
    // JSON.stringify strips undefined → id is absent from the payload
    await store.createGraphNode({
      type: 'Position',
      name: 'DevOps',
      properties: {},
    })

    const callArgs = vi.mocked(request.post).mock.calls[0]
    const payload = callArgs[1] as Record<string, unknown>

    // id must not be in the payload — backend GraphNodeItem has id: str = ""
    // but for create, the id should be absent or empty, not a client-generated value
    expect(payload.id).toBeUndefined()
  })

  it('should send properties with undefined values (axios strips them on wire)', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({
      id: '4:new-3',
      type: 'Skill',
      name: 'TypeScript',
      properties: { name: 'TypeScript' },
      status: 'pending',
    })
    vi.mocked(request.get).mockResolvedValueOnce({ items: [] })

    const store = useGraphNodeStore()
    // GraphNodeEditor builds properties with undefined for empty fields:
    // { category: undefined, proficiency: undefined, description: undefined }
    // In the mock layer, undefined values survive in the JS object.
    // On the wire (axios → JSON.stringify), undefined keys are stripped.
    // The contract test verifies the payload structure before serialization.
    await store.createGraphNode({
      type: 'Skill',
      name: 'TypeScript',
      properties: {
        category: undefined,
        proficiency: undefined,
        description: undefined,
      },
    })

    const callArgs = vi.mocked(request.post).mock.calls[0]
    const payload = callArgs[1] as Record<string, unknown>

    // In the mock, undefined values are present in the object.
    // On the real wire, JSON.stringify strips them → backend receives {}.
    // This test documents the pre-serialization state.
    expect(payload.type).toBe('Skill')
    expect(payload.name).toBe('TypeScript')
    // After JSON serialization, undefined keys disappear.
    // Verify the contract: JSON.stringify(payload.properties) === '{}'
    expect(JSON.parse(JSON.stringify(payload.properties))).toEqual({})
  })

  it('should refresh node list after successful create', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.post).mockResolvedValueOnce({
      id: '4:new-4',
      type: 'Skill',
      name: 'Go',
      properties: { name: 'Go' },
      status: 'pending',
    })
    vi.mocked(request.get).mockResolvedValueOnce({
      items: [{ id: '4:new-4', type: 'Skill', name: 'Go', properties: { name: 'Go' }, status: 'pending' }],
    })

    const store = useGraphNodeStore()
    await store.createGraphNode({ type: 'Skill', name: 'Go', properties: {} })

    // After create, fetchGraphNodes is called to refresh the list
    expect(request.get).toHaveBeenCalledWith('/admin/graph/nodes')
    expect(store.graphNodes).toHaveLength(1)
    expect(store.graphNodes[0].name).toBe('Go')
  })
})

describe('useGraphNodeStore — updateGraphNode contract', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('should PUT /admin/graph/nodes/{id} with full payload', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.put).mockResolvedValueOnce({
      id: '4:abc',
      type: 'Skill',
      name: 'Python3',
      properties: { name: 'Python3', category: 'language' },
      status: 'approved',
    })
    vi.mocked(request.get).mockResolvedValueOnce({ items: [] })

    const store = useGraphNodeStore()
    await store.updateGraphNode('4:abc', {
      type: 'Skill',
      name: 'Python3',
      properties: { category: 'language' },
    })

    expect(request.put).toHaveBeenCalledWith('/admin/graph/nodes/4:abc', {
      type: 'Skill',
      name: 'Python3',
      properties: { category: 'language' },
    })
  })
})

describe('useGraphNodeStore — deleteGraphNode contract', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('should DELETE /admin/graph/nodes/{id}', async () => {
    const request = (await import('@/api/request')).default
    vi.mocked(request.delete).mockResolvedValueOnce({ ok: true, deleted: 1 })
    vi.mocked(request.get).mockResolvedValueOnce({ items: [] })

    const store = useGraphNodeStore()
    await store.deleteGraphNode('4:xyz')

    expect(request.delete).toHaveBeenCalledWith('/admin/graph/nodes/4:xyz')
  })
})