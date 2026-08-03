// pencil-client.js — Direct stdio client for Pencil MCP server
const { spawn } = require('child_process');

class PencilClient {
  constructor() {
    this.proc = null;
    this.output = '';
    this.pending = new Map();
    this.nextId = 1;
    this.ready = false;
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.proc = spawn(
        'D:\\Program File\\Pencil\\resources\\app.asar.unpacked\\out\\mcp-server-windows-x64.exe',
        ['--app', 'desktop', '--agent', 'codexDirect'],
        { stdio: ['pipe', 'pipe', 'pipe'] }
      );

      this.proc.stderr.on('data', () => {}); // suppress stderr

      let buffer = '';
      this.proc.stdout.on('data', (data) => {
        buffer += data.toString();
        // Process complete JSON lines
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line
        for (const line of lines) {
          if (line.trim()) {
            try {
              const msg = JSON.parse(line);
              if (msg.id && this.pending.has(msg.id)) {
                this.pending.get(msg.id)(msg);
                this.pending.delete(msg.id);
              }
            } catch (e) {}
          }
        }
      });

      // Initialize
      this._send('initialize', {
        protocolVersion: '2024-11-05',
        capabilities: {},
        clientInfo: { name: 'codex-pencil-client', version: '1.0.0' }
      }).then((result) => {
        this.ready = true;
        // Send initialized notification
        this.proc.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
        resolve(result);
      }).catch(reject);
    });
  }

  _send(method, params) {
    return new Promise((resolve, reject) => {
      const id = this.nextId++;
      const msg = JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n';
      this.pending.set(id, (response) => {
        if (response.error) reject(new Error(response.error.message));
        else resolve(response.result);
      });
      this.proc.stdin.write(msg);
      // Timeout after 30s
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error('Timeout'));
        }
      }, 30000);
    });
  }

  callTool(name, args) {
    return this._send('tools/call', { name, arguments: args });
  }

  close() {
    if (this.proc) this.proc.kill();
  }
}

// CLI usage
async function main() {
  const client = new PencilClient();
  await client.connect();
  
  const tool = process.argv[2];
  const argsJson = process.argv[3];
  
  if (!tool) {
    console.log('Usage: node pencil-client.js <tool_name> [args_json]');
    console.log('Tools: get_editor_state, batch_get, batch_design, get_guidelines, get_screenshot, get_variables, set_variables, snapshot_layout, export_nodes');
    client.close();
    return;
  }

  const args = argsJson ? JSON.parse(argsJson) : {};
  const result = await client.callTool(tool, args);
  console.log(JSON.stringify(result, null, 2));
  client.close();
}

main().catch(e => { console.error(e.message); process.exit(1); });
