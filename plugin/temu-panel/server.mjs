// temu-panel 插件后端：任务按钮 → spawn Claude Code CLI（headless，cwd=D:\temu-agent）→ 实时日志行。
import http from "node:http";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import readline from "node:readline";

const TEMU_DIR = "D:\\temu-agent";
const STATUS_FILE = path.join(TEMU_DIR, "logs", "last-status.json");
const REPORT_FILE = path.join(TEMU_DIR, "logs", "report-latest.md");

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
  push(`▶ 启动任务 ${def.label} @ ${state.startedAt}`);

  const args = [
    "/c", "claude", "-p", def.prompt,
    "--cwd", TEMU_DIR,
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

const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://127.0.0.1");
  const send = (code, body) => {
    res.writeHead(code, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(body));
  };

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

server.listen(0, "127.0.0.1", () => {
  const { port } = server.address();
  process.stdout.write(JSON.stringify({ ready: true, port }) + "\n");
});
