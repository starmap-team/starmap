import type { Plugin } from 'vite'

/**
 * Vite plugin to add charset=utf-8 to generated CSS files.
 * Fixes potential charset issues with non-ASCII content in styles.
 */
export default function charsetPlugin(): Plugin {
  return {
    name: 'vite-plugin-charset',
    enforce: 'post',
    renderChunk(code, chunk) {
      if (chunk.fileName.endsWith('.css')) {
        return `@charset "UTF-8";\n${code}`
      }
      return null
    },
  }
}