#!/usr/bin/env node
// spawn.mjs: the fleet orchestrator starts new T3 Code sessions (threads), on this machine or another.
// No dependencies. Node >= 22 (global WebSocket). Talks to a running T3 Code server: HTTP to read,
// its WebSocket RPC to start sessions, the same path the T3 Code UI uses.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const NAME_RE = /^[a-z0-9][a-z0-9-]{0,39}$/;
const DEFAULT_PROVIDER = 'claudeAgent';
const DEFAULT_MODEL = 'claude-opus-5-5';
const DEFAULT_EFFORT = 'high';
const TOOL_OF = { claudeAgent: 'claude-code', codex: 'codex' };
const SERVERS_FILE = path.join(os.homedir(), '.config', 'fleet', 'servers.json');
const START_TIMEOUT_MS = 10 * 60 * 1000; // creating a worktree of a big repo takes a while

const USAGE = `usage: node spawn.mjs <command> [options]

  projects                            list the server's projects
  threads [--project <p>] [--last <n>]
                                      list recent threads, newest first (default 10)
  new --as <orchestrator> --project <p> (--worktree | --checkout)
      (--prompt "<text>" | --prompt-file <path>)
      [--name <worker> [--role "<text>"] | --no-fleet] [--title "<text>"]
      [--provider <claudeAgent|codex|...>] [--model <id>] [--effort <low|medium|high|...>] [--plan]
      [--branch <new-branch>] [--base <branch>] [--from-origin] [--no-setup]
                                      start a session and send it the prompt; prints the thread id
  read <thread-id> [--last <n>]       print the thread's last messages (default 4)

  new:
    --as         your fleet name; your card must be the fleet's orchestrator (join --orchestrator)
    --worktree   work in a new git worktree on a new branch (--branch, default t3code/<random>),
                 cut from --base (default: the checkout's current branch); --from-origin cuts it
                 from origin/<base>; the project's setup script runs unless --no-setup
    --checkout   work directly in the project's checkout
    --name       the name the session joins this fleet under (default: made from the title);
                 it replies to you when done
    --no-fleet   the session gets only your prompt and does not join the fleet
    model        ${DEFAULT_PROVIDER} / ${DEFAULT_MODEL} / effort ${DEFAULT_EFFORT} unless --provider, --model, --effort say otherwise

  <p> is a project id, title, folder name or full path.

Server (every command):
  default            the T3 Code server running on this machine; a short-lived token
                     is issued with the "t3" CLI and revoked on exit
  --server <name>    a server from ${SERVERS_FILE}:
                     { "<name>": { "url": "http://<host>:3773", "token": "<bearer>" } }
  --url <origin> --token <bearer>     or T3_URL / T3_TOKEN in the environment`;

function die(msg, code = 1) {
  console.error(`spawn: ${msg}`);
  process.exit(code);
}

function parseArgs(argv) {
  const pos = [];
  const opt = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) opt[a.slice(2)] = true;
      else {
        opt[a.slice(2)] = next;
        i++;
      }
    } else pos.push(a);
  }
  return { pos, opt };
}

const uuid = () => crypto.randomUUID();
const now = () => new Date().toISOString();

// ---- fleet ----

function resolveFleet(opt) {
  const dir = path.resolve(opt.dir || process.env.FLEET_DIR || HERE);
  if (!fs.existsSync(path.join(dir, 'agents'))) die(`not a fleet folder: ${dir}. Run the spawn.mjs copy inside the fleet, or pass --dir <fleet>`);
  return dir;
}

// Only the fleet's orchestrator starts sessions. Its card says so; see "join --orchestrator" in fleet.mjs.
function requireOrchestrator(fleet, name) {
  if (typeof name !== 'string' || !NAME_RE.test(name)) die('missing --as <your fleet name>');
  let card;
  try {
    card = fs.readFileSync(path.join(fleet, 'agents', `${name}.yml`), 'utf8');
  } catch {
    die(`${name} has not joined this fleet`);
  }
  if (!/^orchestrator:\s*"?true"?\s*$/m.test(card)) {
    die(`only the fleet's orchestrator starts sessions, and ${name} is not it. Ask the orchestrator for a new worker instead`);
  }
}

// ---- server and auth ----

function t3(args) {
  try {
    return execFileSync('t3', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  } catch (e) {
    die(`"t3 ${args.join(' ')}" failed: ${e.code === 'ENOENT' ? 't3 CLI not on PATH' : String(e.stderr || e.message).trim()}`);
  }
}

// Returns { url, token, close }. close() revokes a token this script issued itself.
function connect(opt) {
  if (typeof opt.server === 'string') {
    let servers;
    try {
      servers = JSON.parse(fs.readFileSync(SERVERS_FILE, 'utf8'));
    } catch {
      die(`cannot read ${SERVERS_FILE}`);
    }
    const s = servers[opt.server];
    if (!s?.url || !s?.token) die(`no server "${opt.server}" with url and token in ${SERVERS_FILE}. Known: ${Object.keys(servers).join(', ') || 'none'}`);
    return { url: s.url.replace(/\/$/, ''), token: s.token, close() {} };
  }
  const url = opt.url || process.env.T3_URL;
  const token = opt.token || process.env.T3_TOKEN;
  if (url || token) {
    if (!url || !token) die('--url and --token go together');
    return { url: String(url).replace(/\/$/, ''), token: String(token), close() {} };
  }
  const home = process.env.T3CODE_HOME || path.join(os.homedir(), '.t3');
  const runtime = path.join(home, 'userdata', 'server-runtime.json');
  let origin;
  try {
    origin = JSON.parse(fs.readFileSync(runtime, 'utf8')).origin;
  } catch {
    die(`no T3 Code server running here (${runtime} missing). Start T3 Code, or pass --server <name>`);
  }
  // t3 prints a SQLite warning on stderr; the JSON is on stdout.
  const issued = JSON.parse(t3(['auth', 'session', 'issue', '--ttl', '15m', '--label', 'fleet spawn', '--json']));
  return {
    url: origin,
    token: issued.token,
    close() {
      try {
        execFileSync('t3', ['auth', 'session', 'revoke', issued.sessionId], { stdio: 'ignore' });
      } catch {}
    },
  };
}

async function api(srv, method, route, body) {
  let res;
  try {
    res = await fetch(srv.url + route, {
      method,
      headers: { authorization: `Bearer ${srv.token}`, ...(body ? { 'content-type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(15000),
    });
  } catch (e) {
    die(`cannot reach ${srv.url}: ${e.cause?.code || e.message}`);
  }
  const text = await res.text();
  if (!res.ok) die(`${method} ${route} -> HTTP ${res.status}: ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : null;
}

// One call over the server's WebSocket RPC (Effect RPC, JSON framing). The HTTP dispatch endpoint
// skips the UI's bootstrap step, which is what creates the thread and its worktree in one go.
async function rpc(srv, tag, payload, timeoutMs = 15000) {
  if (typeof WebSocket === 'undefined') die(`Node ${process.versions.node} has no WebSocket; use Node 22 or newer`);
  const { ticket } = await api(srv, 'POST', '/api/auth/websocket-ticket');
  const ws = new WebSocket(`${srv.url.replace(/^http/, 'ws')}/ws?wsTicket=${encodeURIComponent(ticket)}`);
  return new Promise((resolve) => {
    const timer = setTimeout(() => die(`${tag}: no answer from ${srv.url} after ${timeoutMs / 1000}s`), timeoutMs);
    ws.onopen = () => ws.send(JSON.stringify({ _tag: 'Request', id: '1', tag, payload, headers: [] }));
    ws.onerror = () => die(`${tag}: WebSocket to ${srv.url} failed`);
    ws.onmessage = (e) => {
      const data = JSON.parse(String(e.data));
      for (const msg of Array.isArray(data) ? data : [data]) {
        if (msg._tag !== 'Exit' || msg.requestId !== '1') continue;
        clearTimeout(timer);
        ws.close();
        if (msg.exit._tag !== 'Success') die(`${tag} failed: ${JSON.stringify(msg.exit.cause ?? msg.exit).slice(0, 600)}`);
        resolve(msg.exit.value);
      }
    };
  });
}

const snapshot = (srv) => api(srv, 'GET', '/api/orchestration/snapshot');
const live = (items) => items.filter((x) => !x.deletedAt);

function findProject(snap, key) {
  if (typeof key !== 'string') die('missing --project <id|title|folder|path>');
  const projects = live(snap.projects);
  const k = key.replace(/\/$/, '');
  const exact = projects.find((p) => p.id === k || p.workspaceRoot === path.resolve(k));
  if (exact) return exact;
  const lc = k.toLowerCase();
  const hits = projects.filter((p) => p.title.toLowerCase() === lc || path.basename(p.workspaceRoot).toLowerCase() === lc);
  if (hits.length === 1) return hits[0];
  if (hits.length > 1) die(`"${key}" matches several projects; use an id:\n${hits.map((p) => `  ${p.id}  ${p.workspaceRoot}`).join('\n')}`);
  die(`no project "${key}". Run "projects" to list them, or add it on that machine with: t3 project add <path>`);
}

function pickModel(opt) {
  if (typeof opt.provider === 'string' && typeof opt.model !== 'string') die('--provider needs --model');
  return {
    instanceId: typeof opt.provider === 'string' ? opt.provider : DEFAULT_PROVIDER,
    model: typeof opt.model === 'string' ? opt.model : DEFAULT_MODEL,
    options: [{ id: 'effort', value: typeof opt.effort === 'string' ? opt.effort : DEFAULT_EFFORT }],
  };
}

function readPrompt(opt) {
  if (typeof opt['prompt-file'] === 'string') return fs.readFileSync(opt['prompt-file'], 'utf8').replace(/^﻿/, '');
  if (typeof opt.prompt === 'string') return opt.prompt;
  die('missing --prompt "<text>" or --prompt-file <path>');
}

// The worker may be on another machine, so it is pointed at the fleet by topic as well as by this machine's path.
function fleetBrief({ fleet, worker, orch, role, tool }) {
  const topic = path.basename(fleet);
  const f = `<fleet>/fleet.mjs`;
  return `You are "${worker}", a worker in the agent fleet "${topic}", started by "${orch}", its orchestrator.

Before the task, join the fleet. Call its folder <fleet>: on ${os.hostname()} it is ${fleet}; on another machine it is the folder "${topic}" under $FLEET_ROOT, or under ~/fleet if FLEET_ROOT is unset. Read <fleet>/PROTOCOL.md in full, then run:
  node ${f} join --as ${worker} --role ${JSON.stringify(role)} --tool ${tool}
Run "node ${f} status --as ${worker} busy --task ..." while you work.

When the task is done (or you are blocked and need ${orch}), report back:
  node ${f} send --as ${worker} --to ${orch} --type reply --subject "<one line>" --body "<result>"
Then set yourself idle and watch your inbox for the next task, as PROTOCOL.md describes.
Do not start new sessions or run spawn.mjs; only ${orch} does that. If the work needs another worker, ask ${orch}.

Task:
`;
}

// A worker name from the title, made unique against the fleet's cards: "Fix refund rounding" -> fix-refund-rounding.
function nameFromTitle(fleet, title) {
  const base = title.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+/, '').slice(0, 36).replace(/-+$/, '') || 'worker';
  const taken = (n) => fs.existsSync(path.join(fleet, 'agents', `${n}.yml`));
  let name = base;
  for (let i = 2; taken(name); i++) name = `${base}-${i}`;
  return name;
}

async function currentBranch(srv, cwd) {
  const res = await rpc(srv, 'vcs.listRefs', { cwd, refKind: 'local' });
  if (!res.isRepo) return { isRepo: false, branch: null };
  return { isRepo: true, branch: res.refs.find((r) => r.current)?.name ?? null };
}

// ---- commands ----

const commands = {
  async projects({ srv }) {
    const rows = live((await snapshot(srv)).projects).map((p) => [p.id, p.title, p.workspaceRoot]);
    if (!rows.length) return console.log('no projects');
    const w = [0, 1].map((i) => Math.max(...rows.map((r) => r[i].length)));
    for (const r of rows) console.log(`${r[0].padEnd(w[0])}  ${r[1].padEnd(w[1])}  ${r[2]}`);
  },

  async threads({ srv, opt }) {
    const snap = await snapshot(srv);
    const project = opt.project ? findProject(snap, opt.project) : null;
    const titles = Object.fromEntries(snap.projects.map((p) => [p.id, p.title]));
    const rows = live(snap.threads)
      .filter((t) => !t.archivedAt && (!project || t.projectId === project.id))
      .sort((a, b) => String(b.updatedAt ?? b.createdAt).localeCompare(String(a.updatedAt ?? a.createdAt)))
      .slice(0, Number(opt.last) || 10);
    for (const t of rows) console.log(`${t.id}  ${titles[t.projectId] ?? '?'}  ${t.branch ?? '-'}  ${t.title}`);
  },

  async new({ srv, opt }) {
    const fleet = resolveFleet(opt);
    requireOrchestrator(fleet, opt.as);
    if (Boolean(opt.worktree) === Boolean(opt.checkout)) die('choose where the session works: --worktree (new branch) or --checkout (the project checkout)');
    if (opt.name !== undefined && (typeof opt.name !== 'string' || !NAME_RE.test(opt.name))) die('bad --name: lowercase letters, digits and hyphens only');
    if (opt.name !== undefined && opt['no-fleet']) die('--name and --no-fleet contradict each other');

    const snap = await snapshot(srv);
    const project = findProject(snap, opt.project);
    const prompt = readPrompt(opt);
    const title = typeof opt.title === 'string' ? opt.title : prompt.trim().split(/\r?\n/)[0].slice(0, 60) || 'New session';
    const modelSelection = pickModel(opt);
    const worker = opt['no-fleet'] ? null : opt.name ?? nameFromTitle(fleet, title);
    const brief = worker
      ? fleetBrief({ fleet, worker, orch: opt.as, role: typeof opt.role === 'string' ? opt.role : title, tool: TOOL_OF[modelSelection.instanceId] || modelSelection.instanceId })
      : '';

    const repo = await currentBranch(srv, project.workspaceRoot);
    let branch = repo.branch;
    let prepareWorktree;
    if (opt.worktree) {
      if (!repo.isRepo) die(`${project.workspaceRoot} is not a git repository, so it cannot have a worktree; use --checkout`);
      const base = typeof opt.base === 'string' ? opt.base : repo.branch;
      if (!base) die('the checkout is on a detached HEAD; pass --base <branch>');
      branch = typeof opt.branch === 'string' ? opt.branch : `t3code/${crypto.randomBytes(4).toString('hex')}`;
      prepareWorktree = { projectCwd: project.workspaceRoot, baseBranch: base, branch, requireWorktree: true, ...(opt['from-origin'] ? { startFromOrigin: true } : {}) };
    }

    const mode = { runtimeMode: 'full-access', interactionMode: opt.plan ? 'plan' : 'default' };
    const threadId = uuid();
    const createdAt = now();
    await rpc(
      srv,
      'orchestration.dispatchCommand',
      {
        type: 'thread.turn.start',
        commandId: uuid(),
        threadId,
        message: { messageId: uuid(), role: 'user', text: brief + prompt.trimEnd(), attachments: [] },
        modelSelection,
        titleSeed: title,
        ...mode,
        bootstrap: {
          createThread: { projectId: project.id, title, modelSelection, ...mode, branch, worktreePath: null, createdAt },
          ...(prepareWorktree ? { prepareWorktree, runSetupScript: !opt['no-setup'] } : {}),
        },
        createdAt,
      },
      START_TIMEOUT_MS,
    );
    const where = prepareWorktree ? `new worktree on ${branch} from ${prepareWorktree.baseBranch}` : `checkout${branch ? ` on ${branch}` : ''}`;
    console.log(`started ${threadId} "${title}" in ${project.title} (${where}; ${modelSelection.model}, effort ${modelSelection.options[0].value}) on ${srv.url}`);
    console.log(worker ? `it joins the fleet as ${worker} and replies to ${opt.as}` : 'it does not join the fleet (--no-fleet)');
  },

  async read({ srv, pos, opt }) {
    if (!pos[1]) die('usage: read <thread-id> [--last <n>]');
    const { thread } = await api(srv, 'GET', `/api/orchestration/threads/${encodeURIComponent(pos[1])}`);
    console.log(`# ${thread.title}${thread.worktreePath ? `  (${thread.branch} at ${thread.worktreePath})` : ''}`);
    for (const m of (thread.messages || []).slice(-(Number(opt.last) || 4))) console.log(`\n--- ${m.role}\n${String(m.text).trimEnd()}`);
  },
};

const { pos, opt } = parseArgs(process.argv.slice(2));
const cmd = commands[pos[0]];
if (!cmd || opt.help) {
  console.log(USAGE);
  process.exit(cmd || pos[0] === 'help' || !pos[0] ? 0 : 1);
}
const srv = connect(opt);
process.on('exit', () => srv.close()); // also runs after die()
await cmd({ srv, pos, opt });
