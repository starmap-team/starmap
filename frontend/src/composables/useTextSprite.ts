/**
 * useTextSprite — Canvas-based text label sprite generator with caching.
 *
 * Extracted from Graph3D.vue to decouple the text rendering pipeline
 * from the component lifecycle.
 */
import type * as THREE from 'three'

// ── Text label cache (key = "name|type") ──
const _textCache = new Map<string, THREE.Texture>()

/** Dispose all cached text textures (call on component unmount). */
export function disposeTextCache() {
  for (const texture of _textCache.values()) texture.dispose()
  _textCache.clear()
}

/**
 * Create a Three.js Sprite with a canvas-rendered text label.
 * Results are cached by `text|nodeType` key — same label reuses the same texture.
 *
 * @param text Label text to render
 * @param nodeRadius Radius of the parent node (used for sprite scaling)
 * @param nodeType 'domain' | 'position' | 'skill' — controls font size & layout
 * @param THREE_NS The THREE namespace (loaded dynamically)
 */
export function createTextSprite(
  text: string,
  nodeRadius: number,
  nodeType: 'domain' | 'position' | 'skill',
  THREE_NS: typeof import('three'),
): import('three').Sprite {
  const cacheKey = `${text}|${nodeType}`
  let texture = _textCache.get(cacheKey)

  if (!texture) {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')!

 // Font sizing based on node type
    const fontSize = nodeType === 'domain' ? 28 : nodeType === 'position' ? 22 : 18
    const lineHeight = fontSize * 1.4
    const maxWidth = nodeType === 'domain' ? 280 : nodeType === 'position' ? 220 : 180
    const paddingX = 16
    const paddingY = 10

    ctx.font = `700 ${fontSize}px 'PingFang SC','Microsoft YaHei','Noto Sans SC',sans-serif`

 // Word-wrap long text
    const words = text.split('')
    const lines: string[] = []
    let currentLine = ''
    for (const ch of words) {
      const testLine = currentLine + ch
      const metrics = ctx.measureText(testLine)
      if (metrics.width > maxWidth && currentLine.length > 0) {
        lines.push(currentLine)
        currentLine = ch
      } else {
        currentLine = testLine
      }
    }
    if (currentLine) lines.push(currentLine)
    if (lines.length === 0) lines.push(text)

    const canvasWidth = maxWidth + paddingX * 2
    const canvasHeight = lines.length * lineHeight + paddingY * 2
    canvas.width = canvasWidth
    canvas.height = canvasHeight

 // Re-apply font after resize
    ctx.font = `700 ${fontSize}px 'PingFang SC','Microsoft YaHei','Noto Sans SC',sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'

 // Draw background pill
    const cornerRadius = 10
    ctx.fillStyle = 'rgba(10, 14, 26, 0.85)'
    roundRect(ctx, 0, 0, canvasWidth, canvasHeight, cornerRadius)
    ctx.fill()

 // Draw border
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.35)'
    ctx.lineWidth = 1.5
    roundRect(ctx, 0.5, 0.5, canvasWidth - 1, canvasHeight - 1, cornerRadius)
    ctx.stroke()

 // Draw text with shadow for readability
    ctx.fillStyle = '#e2e8f0'
    ctx.shadowColor = 'rgba(0, 0, 0, 0.7)'
    ctx.shadowBlur = 4
    ctx.shadowOffsetX = 0
    ctx.shadowOffsetY = 1

    const startY = (canvasHeight - (lines.length - 1) * lineHeight) / 2
    for (let i = 0; i < lines.length; i++) {
      ctx.fillText(lines[i], canvasWidth / 2, startY + i * lineHeight)
    }

    texture = new THREE_NS.CanvasTexture(canvas)
    texture.needsUpdate = true
    _textCache.set(cacheKey, texture)
  }

  const spriteMaterial = new THREE_NS.SpriteMaterial({
    map: texture,
    transparent: true,
    opacity: 0.95,
    depthWrite: false,
  })
  const sprite = new THREE_NS.Sprite(spriteMaterial)

 // Mark as text sprite so hover handler can toggle visibility
  sprite.userData.isTextSprite = true

 // Scale sprite to match node size — larger nodes get proportionally larger labels
  const scaleFactor = nodeType === 'domain' ? 0.18 : nodeType === 'position' ? 0.14 : 0.1
  const img = texture.image as HTMLCanvasElement | undefined
  const aspect = img ? img.width / img.height : 2
  sprite.scale.set(nodeRadius * scaleFactor * aspect, nodeRadius * scaleFactor, 1)

  return sprite
}

/** Canvas roundRect helper for pill-shaped label backgrounds */
function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number, r: number,
) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + w - r, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + r)
  ctx.lineTo(x + w, y + h - r)
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
  ctx.lineTo(x + r, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - r)
  ctx.lineTo(x, y + r)
  ctx.quadraticCurveTo(x, y, x + r, y)
  ctx.closePath()
}
