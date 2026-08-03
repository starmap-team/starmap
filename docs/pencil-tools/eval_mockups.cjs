const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const args = process.argv.slice(2);
if (args.length < 1) {
  console.error('Usage: node eval_mockups.cjs <task> [nodeId]');
  process.exit(1);
}

const task = args[0];
const nodeId = args[1];

function runClient(tool, argsObj) {
  const script = path.resolve(__dirname, 'pencil-client.cjs');
  const argsJson = JSON.stringify(argsObj);
  const r = spawnSync(process.execPath, [script, tool, argsJson], { encoding: 'utf8', env: process.env });
  if (r.error) throw r.error;
  if (r.status !== 0) throw new Error(r.stderr || r.stdout || `pencil-client exited ${r.status}`);
  return JSON.parse(r.stdout);
}

function extractFirstImage(output) {
  if (!output || !Array.isArray(output.content)) return null;
  for (const item of output.content) {
    if (item && item.type === 'image' && item.data) {
      return Buffer.from(item.data, 'base64');
    }
  }
  return null;
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

if (task === 'list-frames') {
  const out = runClient('batch_get', { maxDepth: 1 });
  console.log(JSON.stringify(out, null, 2));
} else if (task === 'screenshot') {
  if (!nodeId) throw new Error('nodeId required for screenshot');
  const out = runClient('get_screenshot', { nodeId });
  const buf = extractFirstImage(out);
  if (!buf) throw new Error('No image returned');
  const outPath = path.resolve(__dirname, `${nodeId}.png`);
  fs.writeFileSync(outPath, buf);
  console.log(outPath);
} else if (task === 'evaluate') {
  if (!nodeId) throw new Error('nodeId required for evaluate');
  const out = runClient('get_screenshot', { nodeId });
  const buf = extractFirstImage(out);
  if (!buf) throw new Error('No image returned');
  const outPath = path.resolve(__dirname, `${nodeId}.png`);
  fs.writeFileSync(outPath, buf);

  const evalDir = path.resolve(__dirname, '..', 'eval');
  ensureDir(evalDir);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const evalPath = path.join(evalDir, `mockup-review-${nodeId}-${stamp}.md`);
  const md = `# Mockup review ${nodeId}\n\n- Source: ${outPath}\n- Generated: ${new Date().toISOString()}\n\n## Visual issues\n\n- (待填写) 覆盖/溢出/断裂/留白/对比度/间距问题\n\n## Structure alignment\n\n- (待填写) 与《星图-项目设计文档v2.0.md》/当前页面结构是否一致\n\n## Anti-AI checklist\n\n- [ ] 无通用占位图标/无情绪化emoji\n- [ ] 排版有节律，非平均堆叠\n- [ ] 层级清晰，主次分明\n- [ ] 微交互/状态变化有预期\n\n## Next iteration\n\n- (待填写) 需要在 Pencil 中修改的具体节点与属性\n`;
  fs.writeFileSync(evalPath, md, 'utf8');
  console.log(JSON.stringify({ screenshot: outPath, review: evalPath }, null, 2));
} else {
  throw new Error(`Unknown task: ${task}`);
}
