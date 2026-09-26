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

## Join

1. **Locate the fleet.** The user gives either a full path or a topic name. A topic name means
   `<root>/<topic>`; if you don't know which one they mean, list the root's subfolders and ask. A
   new topic gets a lowercase, hyphenated folder name. If `<fleet>/PROTOCOL.md` does not exist
   yet, create the fleet with `node <this-skill-dir>/fleet.mjs init <fleet>`. `init` is safe to
   repeat, and safe when two agents run it at the same moment. This step is done when
   `<fleet>/PROTOCOL.md` exists.
2. **Read `<fleet>/PROTOCOL.md` in full.** It holds the layout, the one-writer-per-file rule, the
   message and handoff formats, and the gotchas. It is the same document every agent in the fleet
   works from, including agents that do not have this skill.
3. **Join under a name.** Use the name the user gives. Otherwise build one from your role and
   machine, such as `orch` or `api-laptop`. Run
   `node <fleet>/fleet.mjs join --as <name> --role "<one line>" --tool <claude-code|codex|...>`.
   Tell the user the name you took. Joining is done when `who` lists you.

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

When the user makes you the orchestrator, split the work into tasks that one worker can finish
without asking you anything. Run `who` to see who is available and what they are doing. Send one
task per message. Each task names its goal and its done criterion, points to a context file if it
needs background, and asks for a reply. Track open tasks by message id; replies carry `reply_to`.
Keep a watcher running so replies wake you. When every task you sent has a reply, report the
results to the user.
