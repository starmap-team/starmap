/**
 * useLoopGraph — G6 mini-graph rendering logic for LoopDemo Step 3
 *
 * Extracted from LoopDemo.vue lines 156-389 (~230 lines).
 * Handles: renderMiniGraph, graphContainerRef, graphInstance,
 * entrance/blink animations, interval cleanup.
 *
 * Depends on: loopStore, extractSkillsFromRun, ensureG6Loaded
 */
import { ref, onUnmounted } from 'vue'
import { ensureG6Loaded } from '@/composables/useG6'
import { useLoopStore } from '@/stores/loop'
import { chartColors, cv } from '@/utils/chartTheme'
import { withAlpha } from '@/utils/graphColors'

export function useLoopGraph() {
  const loopStore = useLoopStore()
  const cc = chartColors()

  const graphContainerRef = ref<HTMLElement | null>(null)
  let graphInstance: any = null
  let _enterIntervalId: ReturnType<typeof setInterval> | null = null
  let _blinkIntervalId: ReturnType<typeof setInterval> | null = null

  /** Extract skills from the current run's step 2 data */
  function extractSkillsFromRun(): { skill: string; is_new: boolean; confidence?: number }[] {
    const step2Data = loopStore.currentRun?.steps[1]?.data
    if (!step2Data) return []
    const skills = step2Data.skills ?? []
    return skills.map((s: any) => ({
      skill: s.skill ?? s.name ?? String(s),
      is_new: s.is_new ?? false,
      confidence: s.confidence,
    }))
  }

  /** Render the G6 mini-graph from step 3 data */
  async function renderMiniGraph(targetPosition?: string) {
    if (!graphContainerRef.value) return
    const step3Data = loopStore.currentRun?.steps[2]?.data
    if (!step3Data) return

    const GraphClass = await ensureG6Loaded()

    if (graphInstance) {
      graphInstance.destroy()
      graphInstance = null
    }

    const container = graphContainerRef.value
    const width = container.clientWidth || 600
    const height = 320

    graphInstance = new GraphClass({
      container,
      width,
      height,
      layout: {
        type: 'force',
        preventOverlap: true,
        nodeSize: 30,
        nodeSpacing: 20,
        animate: true,
      },
      node: {
        style: {
          labelFill: cv('--foreground'),
          labelFontSize: 11,
          labelPlacement: 'bottom' as const,
          labelOffsetY: 6,
        },
      },
      edge: {
        style: {
          stroke: cv('--border'),
          lineWidth: 1.5,
          opacity: 0.4,
          endArrow: true,
        },
      },
      behaviors: ['drag-canvas', 'zoom-canvas'],
      plugins: [{
        type: 'tooltip',
        enable: true,
        trigger: 'pointerenter',
        offset: [10, 10],
        style: {
          background: cv('--card'),
          borderRadius: '8px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          padding: '8px 12px',
          fontSize: '12px',
          border: '1px solid ' + cv('--border'),
          color: cv('--foreground'),
        },
      }],
    })

    // Build nodes and edges from step3 data
    const newNodes: any[] = (step3Data.new_nodes ?? []).map((n: any) => ({
      id: n.id ?? n.name,
      style: {
        size: 28,
        fill: cc.success,
        fillOpacity: 0.9,
        stroke: cc.success,
        lineWidth: 2,
        labelText: n.name ?? n.id,
        labelFill: cv('--foreground'),
        shadowColor: withAlpha(cc.success, 0.4),
        shadowBlur: 12,
        cursor: 'pointer' as const,
      },
    }))

    const existingNodes: any[] = (step3Data.existing_nodes ?? []).map((n: any) => ({
      id: n.id ?? n.name,
      style: {
        size: 24,
        fill: cv('--primary'),
        fillOpacity: 0.7,
        stroke: cv('--primary'),
        lineWidth: 1.5,
        labelText: n.name ?? n.id,
        labelFill: cv('--foreground'),
        cursor: 'pointer' as const,
      },
    }))

    const allGraphNodes = [...newNodes, ...existingNodes]
    const allGraphEdges: any[] = [
      ...(step3Data.new_edges ?? []).map((e: any) => ({
        id: `${e.source}-${e.target}-new`,
        source: e.source,
        target: e.target,
        style: {
          stroke: cc.success,
          lineWidth: 2,
          opacity: 0.7,
          lineDash: [4, 4],
          endArrow: true,
        },
      })),
      ...(step3Data.existing_edges ?? []).map((e: any) => ({
        id: `${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        style: {
          stroke: cv('--border'),
          lineWidth: 1.5,
          opacity: 0.4,
          endArrow: true,
        },
      })),
    ]

    // If no structured data, generate mock visualization
    if (allGraphNodes.length === 0) {
      const skills = extractSkillsFromRun()
      skills.forEach((s, i) => {
        allGraphNodes.push({
          id: `skill_${i}`,
          style: {
            size: s.is_new ? 28 : 24,
            fill: s.is_new ? cc.success : cv('--primary'),
            fillOpacity: s.is_new ? 0.9 : 0.7,
            stroke: s.is_new ? cc.success : cv('--primary'),
            lineWidth: s.is_new ? 2 : 1.5,
            labelText: s.skill,
            labelFill: cv('--foreground'),
            shadowColor: s.is_new ? withAlpha(cc.success, 0.4) : undefined,
            shadowBlur: s.is_new ? 12 : 0,
            cursor: 'pointer' as const,
          },
        })
      })
      // Connect position node to skills
      if (allGraphNodes.length > 0) {
        const posId = 'position_node'
        allGraphNodes.unshift({
          id: posId,
          style: {
            size: 36,
            fill: cv('--info'),
            fillOpacity: 0.85,
            stroke: cv('--info'),
            lineWidth: 2,
            labelText: targetPosition || '目标岗位',
            labelFill: cv('--foreground'),
            labelFontSize: 12,
            labelFontWeight: 'bold' as const,
            shadowColor: withAlpha(cv('--info'), 0.3),
            shadowBlur: 12,
            cursor: 'pointer' as const,
          },
        })
        for (let i = 0; i < allGraphNodes.length; i++) {
          if (allGraphNodes[i].id !== posId) {
            allGraphEdges.push({
              id: `${posId}-${allGraphNodes[i].id}`,
              source: posId,
              target: allGraphNodes[i].id,
              style: {
                stroke: cv('--border'),
                lineWidth: 1.5,
                opacity: 0.4,
                endArrow: true,
              },
            })
          }
        }
      }
    }

    if (allGraphNodes.length === 0) return

    // Set initial opacity to 0 for entrance animation
    for (const node of allGraphNodes) {
      node.style.fillOpacity = 0
      node.style.labelOpacity = 0
    }
    graphInstance.setData({ nodes: allGraphNodes, edges: allGraphEdges })
    graphInstance.render()

    // Staggered node entrance animation
    let enterIdx = 0
    _enterIntervalId = setInterval(() => {
      if (!graphInstance || enterIdx >= allGraphNodes.length) {
        if (_enterIntervalId) clearInterval(_enterIntervalId)
        return
      }
      const node = allGraphNodes[enterIdx]
      const isNew = newNodes.some(n => n.id === node.id)
      graphInstance.updateNodeData([{
        id: node.id,
        style: {
          fillOpacity: isNew ? 0.9 : 0.7,
          labelOpacity: 1,
        },
      }])
      graphInstance.draw()
      enterIdx++
    }, 80)

    // Blink animation for new nodes (starts after entrance completes)
    if (newNodes.length > 0) {
      let blinkOn = true
      _blinkIntervalId = setInterval(() => {
        if (!graphInstance) { if (_blinkIntervalId) clearInterval(_blinkIntervalId); return }
        blinkOn = !blinkOn
        for (const n of newNodes) {
          graphInstance.updateNodeData([{
            id: n.id,
            style: {
              fillOpacity: blinkOn ? 0.9 : 0.4,
              shadowBlur: blinkOn ? 16 : 4,
            },
          }])
        }
        graphInstance.draw()
      }, 800)
    }
  }

  /** Destroy the graph instance and clear intervals */
  function destroyGraph() {
    if (graphInstance) {
      graphInstance.destroy()
      graphInstance = null
    }
    if (_enterIntervalId) clearInterval(_enterIntervalId)
    if (_blinkIntervalId) clearInterval(_blinkIntervalId)
  }

  onUnmounted(() => {
    destroyGraph()
  })

  return {
    graphContainerRef,
    renderMiniGraph,
    destroyGraph,
    extractSkillsFromRun,
  }
}
