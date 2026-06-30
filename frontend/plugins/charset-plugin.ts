import type { Plugin } from 'vite'

export default function charsetPlugin(): Plugin {
  return {
    name: 'charset-utf8',
    transformIndexHtml(html) {
      if (!html.includes('charset')) {
        return html.replace('<head>', '<head>\n    <meta charset="UTF-8">')
      }
      return html
    },
  }
}