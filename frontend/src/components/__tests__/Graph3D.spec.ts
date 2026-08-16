/**
 * Graph3D.spec.ts — 3D 节点降噪 LOD + cluster 折叠单元测试
 *
 * 2026-08-13: (M1 全景图谱) Plan 01-03 Task 4
 *
 * 聚焦纯 composable 测试 (useGraph3DLOD / useGraph3DClustering),避免 mount
 * Graph3D.vue 触发 3d-force-graph dynamic import + WebGL 依赖。沿 04-datasources
 * DS-E 教训:mount Graph3D 会触发 3d-force-graph dynamic import,需 stub 模块;
 * 本 plan 不做 mount 集成测试,scope 控制。
 */
import { describe, it, expect } from 'vitest'
import { ref, nextTick } from 'vue'
import {
  useGraph3DLOD,
  clusterNodes3D,
} from '@/composables/graph3d'

describe('useGraph3DLOD', () => {
  it('hides labels when nodeCount > hideLabelsAbove', async () => {
    const lod = useGraph3DLOD({ hideLabelsAbove: 30, simplifyAbove: 100, defaultLabelsVisible: true })
    expect(lod.shouldShowLabels.value).toBe(true)  // default
    lod.setNodeCount(20)
    await nextTick()
    expect(lod.shouldShowLabels.value).toBe(true)
    lod.setNodeCount(50)
    await nextTick()
    expect(lod.shouldShowLabels.value).toBe(false)  // > 30 → hide
  })

  it('simplifies when nodeCount > simplifyAbove', async () => {
    const lod = useGraph3DLOD({ hideLabelsAbove: 30, simplifyAbove: 100, defaultLabelsVisible: true })
    expect(lod.shouldSimplify.value).toBe(false)
    lod.setNodeCount(50)
    await nextTick()
    expect(lod.shouldSimplify.value).toBe(false)  // 50 < 100
    lod.setNodeCount(150)
    await nextTick()
    expect(lod.shouldSimplify.value).toBe(true)   // 150 > 100
  })
})

describe('clusterNodes3D', () => {
  it('returns null cluster when nodeCount ≤ limit * threshold', () => {
    // 25 nodes + limit=30 + threshold=0.8 → 24 threshold; 25 > 24 → cluster
    // 修正: 23 nodes < 24 → no cluster
    const nodes = Array.from({ length: 23 }, (_, i) => ({
      id: `n-${i}`,
      position_count: i + 1,
    }))
    const result = clusterNodes3D(nodes, 30, 0.8)
    expect(result.cluster).toBeNull()
    expect(result.visible).toHaveLength(23)
  })

  it('creates cluster meta-node when nodeCount > limit * threshold', () => {
    // 50 nodes + limit=30 + threshold=0.8 → 24 threshold; 50 > 24 → cluster
    const nodes = Array.from({ length: 50 }, (_, i) => ({
      id: `n-${i}`,
      position_count: 100 - i,  // 降序 so first has highest count
    }))
    const result = clusterNodes3D(nodes, 30, 0.8)
    expect(result.cluster).not.toBeNull()
    // visible = top 30 (保留) + 1 cluster = 31
    expect(result.visible).toHaveLength(31)
    // 最后一个是 cluster
    const lastVisible = result.visible[result.visible.length - 1]
    expect(lastVisible.id).toBe('cluster-overflow')
    expect(lastVisible.color).toBe('#999999')
    expect((lastVisible as unknown as { properties: { name: string } }).properties.name).toContain('more nodes')
  })

  it('cluster meta-node has correct properties (id, color, position_count, name)', () => {
    const nodes = Array.from({ length: 50 }, (_, i) => ({
      id: `n-${i}`,
      position_count: 10,
    }))
    const result = clusterNodes3D(nodes, 30, 0.8)
    expect(result.cluster).not.toBeNull()
    expect(result.cluster!.id).toBe('cluster-overflow')
    expect(result.cluster!.color).toBe('#999999')
    expect(result.cluster!.labels).toEqual(['Cluster'])
    // 50 nodes - 30 visible = 20 overflow; each position_count=10 → cluster.position_count = 200
    expect(result.cluster!.position_count).toBe(200)
    expect(result.cluster!.properties.name).toBe('20 more nodes')
    expect(result.cluster!.properties.children_ids).toHaveLength(20)
  })

  it('sorts visible nodes by position_count DESC before applying limit', () => {
    // 即使传入乱序,clusterNodes3D 应先按 position_count 降序排序
    const nodes = [
      { id: 'low', position_count: 5 },
      { id: 'high', position_count: 100 },
      { id: 'mid', position_count: 50 },
    ]
    const result = clusterNodes3D(nodes, 2, 0.8)  // limit=2 → threshold=1.6; 3 > 1.6 → cluster
    expect(result.cluster).not.toBeNull()
    expect(result.visible).toHaveLength(3)  // top 2 + 1 cluster
    // visible[0] 应是 position_count 最高 (high=100)
    expect(result.visible[0].id).toBe('high')
    expect(result.visible[1].id).toBe('mid')
  })

  it('returns null cluster at exactly threshold boundary', () => {
    // 24 nodes + limit=30 + threshold=0.8 → threshold 24; 24 not > 24 → no cluster
    const nodes = Array.from({ length: 24 }, (_, i) => ({ id: `n-${i}`, position_count: 1 }))
    const result = clusterNodes3D(nodes, 30, 0.8)
    expect(result.cluster).toBeNull()
    expect(result.visible).toHaveLength(24)
  })

  it('handles empty input gracefully', () => {
    const result = clusterNodes3D([], 30, 0.8)
    expect(result.cluster).toBeNull()
    expect(result.visible).toHaveLength(0)
  })
})