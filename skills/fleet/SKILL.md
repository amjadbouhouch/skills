---
name: fleet
description: Coordinate AI agent sessions across machines and tools (Claude Code, Codex) through a shared synced folder, by registering, messaging, handing off context and watching an inbox. Use when the user names a fleet folder or fleet topic; asks to set up or join a fleet; asks to message, brief, delegate to or hand off to another agent or session; or asks to check for, or wait on, messages from other agents.
---

# Fleet

A fleet is a folder that Syncthing keeps in step across machines. Agents coordinate through it
with plain files: each agent keeps a card in `agents/`, receives messages in `inbox/<name>/`, and
shares anything long as a file in `context/`. The folder is the whole system.

Fleets live side by side under one synced **root**, one subfolder per project or topic
(`<root>/<topic>`), so each topic keeps its own agents and messages. On each machine the root is
`$FLEET_ROOT` if that is set, otherwise `~/fleet`. The root itself is not a fleet. It only holds
the fleets and the Syncthing files.

`fleet.mjs` (Node ≥ 18, no dependencies) does the file work. `init` puts a copy in the fleet
folder, and that copy finds the fleet from its own location. Once a fleet exists, run
`node <fleet>/fleet.mjs <command>`; `node <fleet>/fleet.mjs help` lists every command and option.
`init` also copies `spawn.mjs`, which starts new T3 Code sessions from the command line (see
[Starting sessions](#starting-sessions)).

## Join

1. **Locate the fleet.** The user gives either a full path or a topic name. A topic name means
   `<root>/<topic>`; if you don't know which one they mean, list the root's subfolders and ask. A
   new topic gets a lowercase, hyphenated folder name. If `<fleet>/PROTOCOL.md` does not exist
   yet, create the fleet with `node <this-skill-dir>/fleet.mjs init <fleet>`. `init` is safe to
   repeat, and safe when two agents run it at the same moment. This step is done when
   `<fleet>/PROTOCOL.md` exists. **If you created the fleet, you are its orchestrator**: join as
   `orch` unless the user names you otherwise, add `--orchestrator` in step 3, and follow
   [Orchestrating](#orchestrating).
2. **Read `<fleet>/PROTOCOL.md` in full.** It holds the layout, the one-writer-per-file rule, the
   message and handoff formats, and the gotchas. It is the same document every agent in the fleet
   works from, including agents that do not have this skill.
3. **Join under a name.** Use the name the user gives. Otherwise build one from your role and
   machine, such as `orch` or `api-laptop`. Run
   `node <fleet>/fleet.mjs join --as <name> --role "<one line>" --tool <claude-code|codex|...>`,
   plus `--orchestrator` if you created the fleet. A fleet has one orchestrator; `join` refuses a
   second. Tell the user the name you took. Joining is done when `who` lists you.

## Every turn once joined

- **Read your inbox first**, before the user's request: `inbox --as <name>`. This is how messages
  reach you.
- **Handle each message, then mark it `done`.** Answer asks with `send --reply-to <id>`.
- **Keep your card true.** Run `status --as <name> busy --task "…"` while working. Set `idle`
  when you finish, `blocked` when you are waiting on someone, and `offline` when the user ends the
  session.
- **Send long material as a file.** Write it to `context/<name>--<topic>.md` with your file tools,
  then send a short message that names the file. On PowerShell, pass any body that contains quotes
  or line breaks with `--body-file <temp file outside the fleet>`. PowerShell 5.1 mangles embedded
  quotes in native arguments.

## Waiting for messages

A session that has finished its turn reads nothing until something wakes it. `watch --once` is
the wake-up. It exits as soon as your inbox holds an unread message: exit 0 means there is mail,
exit 2 means it timed out. Pick the form that fits your harness:

- **The harness re-invokes you when a background command exits** (Claude Code background Bash):
  run `watch --as <name> --once` in the background, end your turn, and run `inbox` when it fires.
- **The harness streams a long-running command's output** (Claude Code Monitor): run
  `watch --as <name>`. It prints one line per new message.
- **Neither** (Codex, or a subagent that must finish in one go): run `watch --as <name> --once --timeout 540` in the foreground while the
  user wants you to wait, and run it again after each exit 2.

The watcher fires on any unread message, so mark handled messages `done` before you start it
again.

## Orchestrating

You orchestrate when your card is the fleet's orchestrator (`who` marks it with `*`). Split the work
into tasks that one worker can finish without asking you anything. Run `who` to see who is
available and what they are doing. When no idle worker fits a task, start one (see
[Starting sessions](#starting-sessions)) instead of asking the user to open a session. Send one
task per message. Each task names its goal and its done criterion, points to a context file if it
needs background, and asks for a reply. Track open tasks by message id; replies carry `reply_to`.
Keep a watcher running so replies wake you. When every task you sent has a reply, report the
results to the user.

## Starting sessions

`spawn.mjs` starts a new session in T3 Code, on this machine or another, and sends it its first
prompt. The session appears in the T3 Code sidebar like one the user opened. Run
`node <fleet>/spawn.mjs help` for every option.

These rules are strict:

1. **Only the orchestrator starts sessions.** `spawn.mjs new` refuses unless `--as` names the
   fleet's orchestrator. A worker that needs help asks the orchestrator for a new worker, and
   never runs `spawn.mjs` itself.
2. **The model is Claude Opus 5.5 at high effort** (`spawn.mjs` defaults). Pass `--provider`,
   `--model` or `--effort` only when the user has asked for a different model or effort, for
   that session or for the fleet.
3. **Choose where the session works; `spawn.mjs` will not guess.** Pass one of:
   - `--worktree`: a new git worktree on a new branch, cut from the checkout's current branch
     (`--base <branch>` to choose another, `--from-origin` to cut from `origin/<base>`). The
     project's setup script runs in it. **Use this for building a feature or fixing a bug**, and
     whenever two sessions might edit the same project at the same time.
   - `--checkout`: the project's checkout itself. Use it for work that should not live on a new
     branch: reading, investigating, answering questions, running the app or its scripts, or
     continuing work on the branch the checkout is already on.

   If the task fits neither clearly, ask the user which one before you start the session.

Then:

- **Find the project.** `spawn.mjs projects` lists the server's projects. A session can only
  start in a project that T3 Code already knows on that machine. If the one you need is missing,
  ask the user, or run `t3 project add <path>` on that machine.
- **Start a worker** with `spawn.mjs new --as <you> --project <p> --worktree --title "<short>"
  --prompt "<task>"`. Every new session joins the fleet: `spawn.mjs` puts a brief in front of the
  prompt telling it to join, read `PROTOCOL.md`, reply to you when done, and never start
  sessions. Its name comes from the title (`"Fix refund rounding"` → `fix-refund-rounding`) unless
  you pass `--name <worker>`, and `new` prints it. Give the prompt the same done criterion you
  would put in a task message. Pass `--no-fleet` only for a one-off question you will read with
  `spawn.mjs read`; that session gets only your prompt. `--plan` starts it in plan mode.
- **Other machine.** Pass `--server <name>`, defined in `~/.config/fleet/servers.json` as
  `{ "<name>": { "url": "http://<host>:3773", "token": "<bearer>" } }`. The user sets this up
  once. On that machine they start T3 Code so it can be reached (for example `t3 serve --host
  <tailnet-ip>`, or `--tailscale-serve`), and issue a token there with
  `t3 auth session issue --ttl 30d --label orch --token-only`. Without `--server`, `spawn.mjs`
  uses the T3 Code server running locally and issues itself a short-lived token through the `t3`
  CLI. `spawn.mjs` needs Node 22 or newer.
- **Check on it.** The worker's reply reaches your inbox. Keep a watcher running for it, and use
  `who` to see whether the worker has joined. `spawn.mjs threads` shows each session's branch,
  and `spawn.mjs read <thread-id>` prints its latest messages if it seems stuck. T3 Code may
  rename a new `t3code/<random>` branch to fit the task, so read the branch from there, not from
  the `new` output.
- **Sessions run in full-access mode.**
