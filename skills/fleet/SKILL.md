---
name: fleet
description: Coordinate AI agent sessions across machines and tools (Claude Code, Codex) through a shared synced folder, by registering, messaging, handing off context and watching an inbox. Use when the user names a fleet folder or fleet topic; asks to set up or join a fleet; asks to message, brief, delegate to or hand off to another agent or session; or asks to check for, or wait on, messages from other agents.
---

# Fleet

A fleet is a folder that Syncthing keeps in step across machines. Agents coordinate through it
with plain files: each agent keeps a card in `agents/`, receives messages in `inbox/<name>/`, and
shares anything long as a file in `context/`. The folder is the whole system.

Fleets live side by side under one synced **root**, one subfolder per project or topic
(`<root>/<topic>`). The root is `$FLEET_ROOT` if set, otherwise `~/fleet`. The root itself is not
a fleet; it only holds the fleets and the Syncthing files.

`fleet.mjs` (Node ≥ 18, no dependencies) does the file work. `init` copies it, `spawn.mjs` and
`PROTOCOL.md` into the fleet folder, and the copy finds the fleet from its own location: run
`node <fleet>/fleet.mjs <command>` (`help` lists every command and option).

## Join

1. **Locate the fleet.** The user gives a full path or a topic name (`<root>/<topic>`). If you
   can't tell which topic they mean, list the root's subfolders and ask. A new topic gets a
   lowercase, hyphenated name. If `<fleet>/PROTOCOL.md` doesn't exist, create the fleet:
   `node <this-skill-dir>/fleet.mjs init <fleet>` (safe to repeat, safe when two agents race).
   If the fleet exists but has no `spawn.mjs`, its scripts predate this skill: run the same `init`
   to refresh them. Cards, inboxes and context are left alone.
2. **Read `<fleet>/PROTOCOL.md` in full.** It has the layout, the one-writer-per-file rule, the
   message and handoff formats, and the gotchas. Every agent in the fleet works from it, including
   agents without this skill, so it is the authority when this file and it differ.
3. **Join under a name**: the one the user gives, otherwise role + machine (`orch`,
   `api-laptop`).
   `node <fleet>/fleet.mjs join --as <name> --role "<one line>" --tool <claude-code|codex|...>`.
   Tell the user the name you took. Done when `who` lists you.

**If you created the fleet, you are its orchestrator.** Join as `orch` unless the user names you
otherwise, add `--orchestrator` (a fleet has one; `join` refuses a second), and read
[references/orchestrating.md](references/orchestrating.md) before you plan any work. It covers
splitting work, starting sessions with `spawn.mjs`, and waking idle workers. Workers don't need it.

## Every turn once joined

- **Read your inbox first**, before the user's request: `inbox --as <name>`. It's the only way
  messages reach you.
- **Handle each message, then mark it `done`.** Answer asks with `send --reply-to <id>`, so the
  sender can match answers to asks.
- **Keep your card true**: `status --as <name> busy --task "…"` while working; `idle` when done,
  `blocked` when waiting on someone, `offline` when the user ends the session. Other agents plan
  around your card, so a stale `busy` stalls them.
- **Long material goes in a file.** Write `context/<name>--<topic>.md`, then send a short message
  naming it. On PowerShell, pass a body with quotes or line breaks via
  `--body-file <temp file outside the fleet>` (PowerShell 5.1 mangles embedded quotes).
- **Never start sessions yourself** unless you are the orchestrator. Need another worker? Ask it.

## Waiting for messages

A session whose turn has ended reads nothing until something wakes it. `watch --once` is the
wake-up: it exits 0 as soon as your inbox holds an unread message, 2 on timeout. It fires on *any*
unread message, so mark handled ones `done` before re-arming, or it exits immediately. One command
does both: `done --as <name> <id> && watch --as <name> --once --timeout <sec>`.

Pick the form that fits your harness:

- **Harness re-invokes you when a background command exits** (Claude Code background Bash): run
  `watch --as <name> --once` in the background, end your turn, run `inbox` when it fires. Give the
  background call its longest timeout (2 h = 7,200,000 ms) and `watch --timeout` a bit under it
  (`7000`). If the harness kills it anyway, nothing is lost: check `inbox` and re-arm.
- **Harness streams a long-running command's output** (Claude Code Monitor): `watch --as <name>`
  prints one line per new message.
- **Neither** (Codex, or a sub-agent that must finish in one go): run
  `watch --as <name> --once --timeout 540` in the foreground while the user wants you to wait,
  and again after each exit 2. Between turns the orchestrator wakes you by posting into your
  session ("Orch: new message in your inbox (<id>)"): read your inbox then.

## Long-lived processes

A server or training run you start is a child of T3 Code, and a T3 Code restart or reboot kills
it. Run anything that must outlive the session detached (an OS service, or on Windows a logon
scheduled task), and note how to restart it in a context file. For long jobs, keep a short
`STATUS` note there too, so a restarted session can resume.
