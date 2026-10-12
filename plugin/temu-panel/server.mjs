// temu-panel 后端：任务按钮 → spawn Claude Code CLI（headless，cwd=D:\temu-agent）→ 实时日志行。
// 双模式：被 CloudCLI 宿主 spawn（随机端口 + stdout ready 协议）；
//         独立运行 `node server.mjs --port 3790` → 浏览器打开 http://127.0.0.1:3790 即独立工作台。
import http from "node:http";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import readline from "node:readline";

const TEMU_DIR = "D:\\temu-agent";
const STATUS_FILE = path.join(TEMU_DIR, "logs", "last-status.json");
const REPORT_FILE = path.join(TEMU_DIR, "logs", "report-latest.md");

const portArg = process.argv.indexOf("--port");
const STANDALONE_PORT = portArg > -1 ? Number(process.argv[portArg + 1]) : null;

const TASKS = {
  "sync-check": {
    label: "同步体检（只读）",
    prompt: "按照 .claude/skills/temu-sync-check/SKILL.md 定义的流程执行每日同步体检任务（只读，不点任何同步按钮），完成后简短汇报结论。",
  },
};

const state = {
  running: false,
  task: null,
  startedAt: null,
  finishedAt: null,
  exitCode: null,
  lines: [],
  proc: null,
};

function push(line) {
  state.lines.push(line);
  if (state.lines.length > 2000) state.lines.splice(0, state.lines.length - 2000);
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf-8"));
  } catch {
    return null;
  }
}

function startTask(task) {
  if (state.running) return { ok: false, error: "已有任务在运行" };
  const def = TASKS[task];
  if (!def) return { ok: false, error: `未知任务: ${task}` };

  state.running = true;
  state.task = task;
  state.startedAt = new Date().toISOString();
  state.finishedAt = null;
  state.exitCode = null;
  state.lines = [];
  push(`▶ 启动任务 ${def.label} @ ${new Date().toLocaleString()}`);

  const args = [
    "/c", "claude", "-p", def.prompt,
    "--permission-mode", "bypassPermissions",
    "--output-format", "stream-json",
    "--verbose",
  ];
  const env = { ...process.env };
  const npmGlobal = path.join(os.homedir(), "AppData", "Roaming", "npm");
  env.PATH = `${npmGlobal};${env.PATH || ""}`;

  const child = spawn(process.env.ComSpec || "cmd.exe", args, { env, cwd: TEMU_DIR });
  state.proc = child;

  const rl = readline.createInterface({ input: child.stdout });
  rl.on("line", (raw) => {
    try {
      const ev = JSON.parse(raw);
      if (ev.type === "assistant" && Array.isArray(ev.message?.content)) {
        for (const block of ev.message.content) {
          if (block.type === "text" && block.text) push(block.text);
          if (block.type === "tool_use") push(`🔧 ${block.name} ${JSON.stringify(block.input || {}).slice(0, 160)}`);
        }
      } else if (ev.type === "result") {
        push(ev.result ? String(ev.result).slice(0, 2000) : "(空结果)");
      }
    } catch {
      push(raw.slice(0, 500));
    }
  });
  const rlErr = readline.createInterface({ input: child.stderr });
  rlErr.on("line", (l) => push(`⚠ ${l.slice(0, 300)}`));

  child.on("close", (code) => {
    state.running = false;
    state.finishedAt = new Date().toISOString();
    state.exitCode = code;
    push(`■ 任务结束 exit=${code}`);
    const st = readJson(STATUS_FILE);
    if (st) push(`📄 报告: ${st.report} | ok=${st.ok} | ${st.summary || ""}`);
  });

  return { ok: true };
}

const STANDALONE_HTML = `<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>TEMU 工作台（独立版）</title>
<style>
  body { font-family: system-ui, "Microsoft YaHei", sans-serif; background: #1b1e24; color: #ddd; margin: 0; padding: 24px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: #888; font-size: 12px; margin-bottom: 16px; }
  #state { font-size: 14px; margin: 8px 0 2px; } #last { font-size: 12px; color: #999; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; margin: 14px 0; max-width: 960px; }
  .card { border: 1px solid #3a3f4a; border-radius: 10px; padding: 14px; cursor: pointer; background: #22262e; transition: .15s; }
  .card:hover { border-color: #4a9eff; transform: translateY(-1px); }
  .card.disabled { opacity: .35; cursor: not-allowed; }
  .card h4 { margin: 0 0 6px; font-size: 14px; } .card p { margin: 0; font-size: 12px; color: #999; }
  #log { background: #10131a; color: #9fd49f; border-radius: 8px; padding: 12px; height: 300px; overflow-y: auto;
         font: 12px/1.5 Consolas, monospace; white-space: pre-wrap; max-width: 960px; }
  .sec { margin: 16px 0 6px; font-size: 14px; } button { background: #2b6cb0; color: #fff; border: 0; border-radius: 6px;
         padding: 6px 16px; cursor: pointer; margin-left: 8px; }
  button:hover { background: #3a7fc0; }
  #report { background: #141820; border-radius: 8px; padding: 12px; font-size: 12px; white-space: pre-wrap;
            max-height: 240px; overflow-y: auto; max-width: 960px; }
</style></head><body>
<h1>TEMU 工作台</h1>
<div class="sub">computer-use 驱动日常 Edge · 零自动化参数 · 改数据操作永远不进面板（走对话确认）</div>
<div id="state">…</div><div id="last"></div>
<div class="grid" id="grid"></div>
<div class="sec">运行日志 <button onclick="fetch('/stop',{method:'POST'})">停止</button></div>
<div id="log"></div>
<div class="sec">最近报告 <button onclick="loadReport()">刷新</button></div>
<div id="report">（点"刷新"加载）</div>
<script>
const PLACEHOLDERS = [["make-links","插件做链接"],["compliance","合规填写"],["collect-links","商品采集"],["price-review","价格报表"],["new-listing","上新"]];
let lineCount = 0;
async function refresh() {
  try {
    const st = await (await fetch('/status')).json();
    document.getElementById('state').textContent = st.running
      ? '🟢 运行中: ' + st.task + '（' + new Date(st.startedAt).toLocaleTimeString() + ' 起）'
      : '⚪ 空闲（上次 exit=' + (st.exitCode ?? '-') + (st.finishedAt ? '，' + new Date(st.finishedAt).toLocaleTimeString() : '') + '）';
    if (st.lastStatus) document.getElementById('last').textContent =
      '上次任务: ' + st.lastStatus.task + ' ' + (st.lastStatus.ok ? '✅' : '❌') + ' ' + st.lastStatus.ts;
    const data = await (await fetch('/lines?since=' + lineCount)).json();
    if (data.lines.length) {
      const log = document.getElementById('log');
      log.textContent += data.lines.join('\\n') + '\\n';
      lineCount = data.total; log.scrollTop = log.scrollHeight;
    }
  } catch (e) { document.getElementById('state').textContent = '服务不可达: ' + e; }
}
async function run(task, label) {
  if (!confirm('运行「' + label + '」？（只读任务，不点任何同步按钮）')) return;
  lineCount = 0; document.getElementById('log').textContent = '';
  await fetch('/run', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ task }) });
  refresh();
}
async function loadReport() {
  const r = await (await fetch('/report')).json();
  document.getElementById('report').textContent = r.report;
}
function card(id, label, desc, enabled) {
  const c = document.createElement('div');
  c.className = 'card' + (enabled ? '' : ' disabled');
  c.innerHTML = '<h4></h4><p></p>';
  c.querySelector('h4').textContent = label; c.querySelector('p').textContent = desc;
  if (enabled) c.onclick = () => run(id, label);
  return c;
}
const grid = document.getElementById('grid');
grid.appendChild(card('sync-check', '同步体检（只读）', '登录态 + 双按钮验证 + 截图 + 中文报告', true));
for (const [id, label] of PLACEHOLDERS) grid.appendChild(card(id, label, '待发现会话', false));
refresh(); setInterval(refresh, 1500);
</script></body></html>`;

const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://127.0.0.1");
  const send = (code, body) => {
    res.writeHead(code, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(body));
  };

  if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/index.html")) {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(STANDALONE_HTML);
  }
  if (req.method === "GET" && url.pathname === "/status") {
    return send(200, {
      running: state.running,
      task: state.task,
      startedAt: state.startedAt,
      finishedAt: state.finishedAt,
      exitCode: state.exitCode,
      lines: state.lines.length,
      tasks: Object.entries(TASKS).map(([id, t]) => ({ id, label: t.label })),
      lastStatus: readJson(STATUS_FILE),
    });
  }
  if (req.method === "GET" && url.pathname === "/lines") {
    const since = Number(url.searchParams.get("since") || 0);
    return send(200, { lines: state.lines.slice(since), total: state.lines.length });
  }
  if (req.method === "GET" && url.pathname === "/report") {
    try {
      return send(200, { report: fs.readFileSync(REPORT_FILE, "utf-8") });
    } catch {
      return send(200, { report: "(尚无报告)" });
    }
  }
  if (req.method === "POST" && url.pathname === "/run") {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      try {
        return send(200, startTask(JSON.parse(body).task));
      } catch (e) {
        return send(400, { ok: false, error: String(e) });
      }
    });
    return;
  }
  if (req.method === "POST" && url.pathname === "/stop") {
    if (state.proc) {
      state.proc.kill();
      push("⛔ 手动停止");
    }
    return send(200, { ok: true });
  }
  send(404, { error: "not found" });
});

if (STANDALONE_PORT) {
  server.listen(STANDALONE_PORT, "127.0.0.1", () => {
    console.log(`TEMU 工作台（独立版）: http://127.0.0.1:${STANDALONE_PORT}`);
  });
} else {
  server.listen(0, "127.0.0.1", () => {
    const { port } = server.address();
    process.stdout.write(JSON.stringify({ ready: true, port }) + "\n");
  });
}
