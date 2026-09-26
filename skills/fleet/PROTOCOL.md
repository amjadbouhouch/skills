# Fleet protocol

This folder is a **fleet**: AI agent sessions (Claude Code, Codex, any tool, on any machine)
coordinate through it with plain files. Syncthing copies it between machines, usually within
seconds. There is no server. These files are the whole system.

`fleet.mjs` (Node ≥ 18, no dependencies) does all of the file work below, so every agent writes
the same format. Run the copy that sits in this folder: `node <this-folder>/fleet.mjs help`.

## Joining

1. Pick a name: lowercase letters, digits, hyphens (`orch`, `api-laptop`). Use the one the user
   gave you if they gave one.
2. `node fleet.mjs join --as <name> --role "<what you do, one line>" --tool <claude-code|codex|...>`
3. Tell the user the name you took. Every later command carries `--as <name>`.

`join` refuses a name that is live on another machine. Pick a different name, or pass `--force` if
you really are that agent and are resuming on a new machine.

## Layout

```
PROTOCOL.md          this file
fleet.mjs            the helper
agents/<name>.yml    one card per agent: role, status, current task, last_seen
inbox/<name>/        messages for <name>, oldest first by filename
inbox/<name>/done/   messages <name> has handled
context/             plans, handoffs, findings, anything longer than a message
```

## One writer per file

Syncthing cannot merge two machines' edits to one file. It keeps one version and saves the other
as a `.sync-conflict-…` copy. So every file here has exactly one writer:

| File                                | Written by                                                       |
| ----------------------------------- | ---------------------------------------------------------------- |
| `agents/<name>.yml`                 | `<name>` only                                                    |
| a message                           | its sender, once. It is never edited; a reply is a new message   |
| moves or deletes in `inbox/<name>/` | `<name>` only. Everyone else only adds files there               |
| `context/<author>--<topic>.md`      | `<author>` only. To build on it, write your own file and link it |

## Messages

`inbox/<to>/<utc-stamp>--<from>--<id>.md`, for example
`2026-09-27T14-12-00.000Z--orch--7f3a2c.md`. The stamp is ISO time with `:` replaced by `-`,
because Windows does not allow colons in filenames. It makes filename order the same as send order.

```markdown
---
id: 7f3a2c
from: orch
to: api-laptop
type: task # task | reply | question | handoff | note
subject: Fix the refund rounding bug
reply_to: null # the id being answered, on replies
created: "2026-09-27T14:12:00.000Z"
---
Refunds round down instead of half-up. Done = the failing test in refunds.test.ts passes.
Background in context/orch--refunds.md. Reply with the commit hash.
```

- **A message is what the reader acts on**: the ask, what "done" means, where the detail is.
  Plans, logs, diffs, findings and handoffs go in a context file that the message names. A context
  file can be updated; a message cannot.
- **A task names its done criterion and who to reply to.** A worker that finishes replies with
  `--reply-to <id>`, so the sender can match answers to asks.
- **Handled means moved to `done/`** (`node fleet.mjs done --as <name> <id>`). Anything still in
  `inbox/<name>/` is unread. That is the only read flag.

## Handoffs

When a session passes its work to another, the handoff is a context file,
`context/<author>--handoff-<topic>.md`, plus a `handoff` message that points to it:

```markdown
# Handoff: <topic>

Goal: what finished looks like
State: what is done, what is in flight, what is broken right now
Decisions: what was chosen, and why (the reasons are what gets lost between sessions)
Next: the next concrete steps, in order
Where: repo, branch, files, commands to run, open questions
```

Write it for a reader who has none of your context. Your conversation is not in this folder.

## Status

Keep your card current: `status --as <name> busy --task "<text>"` while working, `idle` when done,
`blocked` when you are waiting on someone, `offline` before your session ends. Every command
refreshes `last_seen`, so a card that has not been seen for hours belongs to an agent that is
asleep or gone. Its inbox still waits for it.

## Waiting for messages

An agent between turns reads nothing, so something has to wake it. `watch --as <name> --once`
exits as soon as your inbox has an unread message: exit 0 means there is mail, exit 2 means the
`--timeout` ran out. It fires on any unread message, so mark every handled message `done` before
you start watching again, or it exits straight away.

## By hand (no Node)

Everything above is plain files. Write cards and messages yourself in the formats shown. Write to
a name starting with `.tmp-` in the same folder and then rename it into place, so no reader sees
half a file. `.stignore` stops Syncthing from syncing `.tmp-*` files.

## Gotchas

- **Names are lowercase** because the Windows and macOS filesystems ignore case and Linux does
  not. On the first two, `Orch` and `orch` would be one inbox; on Linux they would be two.
- **Stamps come from each machine's clock**, so order across machines is approximate.
- **`.stignore` is not synced by Syncthing.** `join` writes it on each machine.
- **If writes here are denied**, your sandbox does not include this folder. Ask the user to allow
  it. Codex: start it with `--add-dir <this-folder>`.
- **Garbled accents in a message** usually come from the shell's console encoding, not the file.
  The file itself is UTF-8, so read it directly.
