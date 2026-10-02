#!/usr/bin/env node
// fleet.mjs: file-based coordination for AI agent sessions sharing a synced folder.
// No dependencies. Node >= 18. Rules and formats: PROTOCOL.md next to this file.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const SELF = fileURLToPath(import.meta.url);
const HERE = path.dirname(SELF);
const NAME_RE = /^[a-z0-9][a-z0-9-]{0,39}$/;
const TYPES = ['task', 'reply', 'question', 'handoff', 'note'];
const STATUSES = ['idle', 'busy', 'blocked', 'offline'];
const LIVE_MS = 15 * 60 * 1000; // a card seen this recently belongs to a running agent
const STIGNORE = '(?d).tmp-*';

const USAGE = `usage: node fleet.mjs <command> [options]

  init <dir>                          create a fleet folder (or refresh its PROTOCOL.md, fleet.mjs, spawn.mjs)
  join --as <name> --role "<text>" [--tool <claude-code|codex|...>] [--orchestrator] [--force]
                                      --orchestrator: you run this fleet and alone start sessions
  who                                 list agents, their status and unread counts
  status --as <name> <idle|busy|blocked|offline> [--task "<text>"]
  send --as <name> --to <name[,name]|all> --subject "<text>"
       [--type task|reply|question|handoff|note] [--reply-to <id>]
       (--body "<text>" | --body-file <path>)
  inbox --as <name> [--brief]         print unread messages, oldest first
  done --as <name> <id...> | --all    mark messages handled (moves them to done/)
  watch --as <name> [--once] [--timeout <sec>] [--every <sec>]
                                      report new messages; --once exits 0 on the first,
                                      2 on timeout (no --timeout: waits indefinitely)

The fleet is the folder this script sits in, unless --dir <path> or FLEET_DIR says otherwise.`;

function die(msg, code = 1) {
  console.error(`fleet: ${msg}`);
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

// ---- flat "key: value" YAML, the only shape cards and frontmatter use ----

function fmt(v) {
  if (v === null || v === undefined || v === '') return 'null';
  const s = String(v);
  if (/^[A-Za-z0-9._\/-]+$/.test(s) && !/^(null|true|false|~|[-+.]?\d.*)$/i.test(s)) return s;
  return JSON.stringify(s);
}

function dumpFields(obj) {
  return Object.entries(obj).map(([k, v]) => `${k}: ${fmt(v)}`).join('\n') + '\n';
}

function parseValue(raw) {
  let v = raw.trim();
  if (v.startsWith('"')) {
    const m = v.match(/^"(?:[^"\\]|\\.)*"/);
    if (m) {
      try {
        return JSON.parse(m[0]);
      } catch {}
    }
  }
  v = v.replace(/\s+#.*$/, '').trim();
  if (v.length >= 2 && v.startsWith("'") && v.endsWith("'")) return v.slice(1, -1).replace(/''/g, "'");
  if (v === '' || v === 'null' || v === '~') return null;
  return v;
}

function parseFields(text) {
  const out = {};
  for (const line of text.split(/\r?\n/)) {
    const m = line.match(/^([A-Za-z_][\w-]*):(.*)$/);
    if (m) out[m[1]] = parseValue(m[2]);
  }
  return out;
}

function parseMessage(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  return m ? { meta: parseFields(m[1]), body: m[2] } : { meta: {}, body: text };
}

// ---- filesystem ----

// Write beside the target under a .tmp- name, then rename: a reader (or Syncthing) never sees half a file.
function writeAtomic(file, content) {
  const tmp = path.join(path.dirname(file), `.tmp-${crypto.randomBytes(4).toString('hex')}`);
  fs.writeFileSync(tmp, content);
  fs.renameSync(tmp, file);
}

// Syncthing reads .stignore only at the root of a synced folder (the directory holding .stfolder),
// and a fleet is often a subfolder of that root. Fall back to the fleet itself if no marker is found.
function syncRoot(fleet) {
  for (let dir = fleet; ; dir = path.dirname(dir)) {
    if (fs.existsSync(path.join(dir, '.stfolder'))) return dir;
    if (path.dirname(dir) === dir) return fleet;
  }
}

function ensureStignore(fleet) {
  const file = path.join(syncRoot(fleet), '.stignore');
  const text = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : '';
  if (text.split(/\r?\n/).includes(STIGNORE)) return;
  const sep = text && !text.endsWith('\n') ? '\n' : '';
  fs.writeFileSync(file, `${text}${sep}// fleet: never sync half-written files\n${STIGNORE}\n`);
}

function resolveFleet(opt) {
  const dir = path.resolve(opt.dir || process.env.FLEET_DIR || HERE);
  if (!fs.existsSync(path.join(dir, 'agents'))) {
    die(`not a fleet folder: ${dir}\nrun "node fleet.mjs init <dir>" first, or pass --dir <fleet>`);
  }
  return dir;
}

const cardFile = (fleet, name) => path.join(fleet, 'agents', `${name}.yml`);
const inboxDir = (fleet, name) => path.join(fleet, 'inbox', name);
const now = () => new Date().toISOString();
const ageMs = (iso) => (iso ? Date.now() - Date.parse(iso) : Infinity);

function readCard(fleet, name) {
  try {
    return parseFields(fs.readFileSync(cardFile(fleet, name), 'utf8'));
  } catch {
    return null;
  }
}

function writeCard(fleet, card) {
  writeAtomic(cardFile(fleet, card.name), `# written only by ${card.name}; see PROTOCOL.md\n${dumpFields(card)}`);
}

function listCards(fleet) {
  const dir = path.join(fleet, 'agents');
  const names = fs.readdirSync(dir).filter((f) => f.endsWith('.yml') && !f.startsWith('.'));
  for (const f of names.filter((f) => f.includes('.sync-conflict-'))) {
    console.error(`fleet: warning: conflict copy agents/${f}; two machines wrote one card. Its owner should delete it.`);
  }
  return names
    .filter((f) => !f.includes('.sync-conflict-'))
    .map((f) => readCard(fleet, f.slice(0, -4)))
    .filter(Boolean)
    .sort((a, b) => String(a.name).localeCompare(String(b.name)));
}

function unread(fleet, name) {
  const dir = inboxDir(fleet, name);
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isFile() && e.name.endsWith('.md') && !e.name.startsWith('.'))
    .map((e) => e.name)
    .sort();
}

const isOrchestrator = (card) => String(card?.orchestrator) === 'true';

const idOf = (file) => file.slice(0, -3).split('--').pop();

function needName(opt) {
  const name = opt.as;
  if (typeof name !== 'string') die('missing --as <your-name>');
  if (!NAME_RE.test(name)) die(`bad name "${name}": lowercase letters, digits and hyphens only`);
  return name;
}

// Every command run as an agent refreshes its last_seen, so the card doubles as a heartbeat.
function touch(fleet, name) {
  const card = readCard(fleet, name);
  if (!card) die(`${name} has not joined this fleet; run: join --as ${name} --role "..."`);
  card.last_seen = now();
  writeCard(fleet, card);
  return card;
}

function fmtAge(ms) {
  if (!Number.isFinite(ms)) return '?';
  const m = Math.floor(ms / 60000);
  if (m < 1) return 'now';
  if (m < 60) return `${m}m`;
  if (m < 48 * 60) return `${Math.floor(m / 60)}h`;
  return `${Math.floor(m / 1440)}d`;
}

// ---- commands ----

const commands = {
  init({ pos }) {
    if (!pos[1]) die('usage: init <dir>');
    const dir = path.resolve(pos[1]);
    for (const d of ['agents', 'inbox', 'context']) fs.mkdirSync(path.join(dir, d), { recursive: true });
    for (const f of ['PROTOCOL.md', 'fleet.mjs', 'spawn.mjs']) {
      const from = path.join(HERE, f);
      const to = path.join(dir, f);
      if (path.resolve(from) !== path.resolve(to)) fs.copyFileSync(from, to);
    }
    ensureStignore(dir);
    console.log(`fleet ready: ${dir}\nnext: node "${path.join(dir, 'fleet.mjs')}" join --as <name> --role "..." --tool <claude-code|codex|...>`);
  },

  join({ opt }) {
    const fleet = resolveFleet(opt);
    const name = needName(opt);
    const old = readCard(fleet, name);
    const host = os.hostname();
    const live = old && old.status !== 'offline' && ageMs(old.last_seen) < LIVE_MS;
    if (live && old.machine !== host && !opt.force) {
      die(
        `${name} is live on ${old.machine} (last seen: ${fmtAge(ageMs(old.last_seen))}). ` +
          `Pick another name, or add --force if you are that agent resuming here.`,
      );
    }
    // A fleet has one orchestrator, the only agent that starts sessions (spawn.mjs checks this field).
    const orchestrator = Boolean(opt.orchestrator) || isOrchestrator(old);
    const rival = orchestrator && listCards(fleet).find((c) => c.name !== name && isOrchestrator(c));
    if (rival && !opt.force) die(`${rival.name} is already this fleet's orchestrator. Join without --orchestrator, or add --force to take over`);
    const t = now();
    writeCard(fleet, {
      name,
      role: typeof opt.role === 'string' ? opt.role : old?.role ?? null,
      tool: typeof opt.tool === 'string' ? opt.tool : old?.tool ?? null,
      machine: host,
      ...(orchestrator ? { orchestrator: 'true' } : {}),
      status: 'idle',
      task: null,
      joined: old?.joined ?? t,
      last_seen: t,
    });
    fs.mkdirSync(path.join(inboxDir(fleet, name), 'done'), { recursive: true });
    ensureStignore(fleet);
    console.log(`joined as ${name}${orchestrator ? ' (orchestrator)' : ''} on ${host}. unread: ${unread(fleet, name).length}`);
  },

  who({ opt }) {
    const fleet = resolveFleet(opt);
    const cards = listCards(fleet);
    if (!cards.length) return console.log('no agents yet');
    const rows = [['NAME', 'STATUS', 'SEEN', 'UNREAD', 'TOOL', 'MACHINE', 'ROLE / TASK']];
    for (const c of cards) {
      const doing = [c.role, c.task && `now: ${c.task}`].filter(Boolean).join(' | ');
      rows.push([isOrchestrator(c) ? `${c.name}*` : c.name, c.status ?? '?', fmtAge(ageMs(c.last_seen)), String(unread(fleet, c.name).length), c.tool ?? '?', c.machine ?? '?', doing]);
    }
    const widths = rows[0].map((_, i) => Math.max(...rows.map((r) => r[i].length)));
    for (const r of rows) console.log(r.map((v, i) => (i === r.length - 1 ? v : v.padEnd(widths[i]))).join('  '));
    if (cards.some(isOrchestrator)) console.log('* orchestrator');
  },

  status({ pos, opt }) {
    const fleet = resolveFleet(opt);
    const name = needName(opt);
    const status = pos[1];
    if (!STATUSES.includes(status)) die(`status must be one of: ${STATUSES.join(', ')}`);
    const card = touch(fleet, name);
    card.status = status;
    if (typeof opt.task === 'string') card.task = opt.task;
    else if (status === 'idle' || status === 'offline') card.task = null;
    writeCard(fleet, card);
    console.log(`${name}: ${status}${card.task ? ` (${card.task})` : ''}`);
  },

  send({ opt }) {
    const fleet = resolveFleet(opt);
    const from = needName(opt);
    touch(fleet, from);
    if (typeof opt.to !== 'string') die('missing --to <name[,name]|all>');
    if (typeof opt.subject !== 'string') die('missing --subject "<text>"');
    const type = typeof opt.type === 'string' ? opt.type : opt['reply-to'] ? 'reply' : 'note';
    if (!TYPES.includes(type)) die(`type must be one of: ${TYPES.join(', ')}`);

    let body;
    if (typeof opt['body-file'] === 'string') body = fs.readFileSync(opt['body-file'], 'utf8').replace(/^﻿/, ''); // PowerShell 5.1 writes a BOM
    else if (typeof opt.body === 'string') body = opt.body;
    else die('missing --body "<text>" or --body-file <path>');

    const known = listCards(fleet).map((c) => c.name);
    const to = opt.to === 'all' ? known.filter((n) => n !== from) : opt.to.split(',').map((s) => s.trim());
    const unknown = to.filter((n) => !known.includes(n));
    if (unknown.length) die(`not in the fleet: ${unknown.join(', ')}. Known: ${known.join(', ') || 'none'}`);
    if (!to.length) die('no recipients');

    const id = crypto.randomBytes(3).toString('hex');
    const created = now();
    const stamp = created.replace(/:/g, '-');
    for (const name of to) {
      const meta = { id, from, to: name, type, subject: opt.subject, reply_to: opt['reply-to'] ?? null, created };
      const dir = inboxDir(fleet, name);
      fs.mkdirSync(dir, { recursive: true });
      writeAtomic(path.join(dir, `${stamp}--${from}--${id}.md`), `---\n${dumpFields(meta)}---\n${body.trimEnd()}\n`);
    }
    console.log(`sent ${id} (${type}) to ${to.join(', ')}`);
  },

  inbox({ opt }) {
    const fleet = resolveFleet(opt);
    const name = needName(opt);
    touch(fleet, name);
    const files = unread(fleet, name);
    if (!files.length) return console.log('no unread messages');
    for (const f of files) {
      const text = fs.readFileSync(path.join(inboxDir(fleet, name), f), 'utf8');
      if (opt.brief) {
        const { meta } = parseMessage(text);
        console.log(`${meta.id ?? idOf(f)}  ${meta.type ?? '?'}  from ${meta.from ?? '?'}: ${meta.subject ?? ''}`);
      } else console.log(`===== inbox/${name}/${f}\n${text.trimEnd()}\n`);
    }
    console.log(`${files.length} unread. When handled: node "${SELF}" done --as ${name} <id...>`);
  },

  done({ pos, opt }) {
    const fleet = resolveFleet(opt);
    const name = needName(opt);
    touch(fleet, name);
    const files = unread(fleet, name);
    const ids = opt.all ? files.map(idOf) : pos.slice(1);
    if (!ids.length) die('usage: done --as <name> <id...> | --all');
    const doneDir = path.join(inboxDir(fleet, name), 'done');
    fs.mkdirSync(doneDir, { recursive: true });
    for (const id of ids) {
      const f = files.find((x) => idOf(x) === id);
      if (!f) {
        console.error(`fleet: no unread message ${id}`);
        continue;
      }
      fs.renameSync(path.join(inboxDir(fleet, name), f), path.join(doneDir, f));
      console.log(`done ${id}`);
    }
  },

  async watch({ opt }) {
    const fleet = resolveFleet(opt);
    const name = needName(opt);
    touch(fleet, name);
    const every = Math.max(1, Number(opt.every) || 5) * 1000;
    const timeout = opt.timeout ? Number(opt.timeout) * 1000 : Infinity;
    const start = Date.now();
    const seen = new Set();
    let beat = Date.now();
    for (;;) {
      const fresh = unread(fleet, name).filter((f) => !seen.has(f));
      for (const f of fresh) {
        seen.add(f);
        const { meta } = parseMessage(fs.readFileSync(path.join(inboxDir(fleet, name), f), 'utf8'));
        console.log(`new message ${meta.id ?? idOf(f)} (${meta.type ?? '?'}) from ${meta.from ?? '?'}: ${meta.subject ?? ''}`);
      }
      if (opt.once && fresh.length) {
        console.log(`read it: node "${SELF}" inbox --as ${name}`);
        process.exit(0);
      }
      if (Date.now() - start >= timeout) {
        console.log('no new messages (timeout)');
        process.exit(2);
      }
      if (Date.now() - beat >= 60000) {
        touch(fleet, name);
        beat = Date.now();
      }
      await new Promise((r) => setTimeout(r, Math.min(every, Math.max(0, timeout - (Date.now() - start)))));
    }
  },
};

const { pos, opt } = parseArgs(process.argv.slice(2));
const cmd = commands[pos[0]];
if (!cmd || opt.help) {
  console.log(USAGE);
  process.exit(cmd || pos[0] === 'help' || !pos[0] ? 0 : 1);
}
await cmd({ pos, opt });
