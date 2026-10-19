# Orchestrating a fleet

Read this when your card is the fleet's orchestrator (`who` marks it with `*`). The basics in
SKILL.md and `PROTOCOL.md` still apply; this adds what only the orchestrator does.

- [Running the work](#running-the-work)
- [Starting sessions](#starting-sessions)
- [Waking and steering workers](#waking-and-steering-workers)

## Running the work

Split the work into tasks one worker can finish without asking you anything. Run `who` to see who
is available. When no idle worker fits, start one ([Starting sessions](#starting-sessions)) rather
than asking the user to open a session. Send one task per message: its goal, its done criterion,
a context file if it needs background, and a request to reply. Track open tasks by message id
(replies carry `reply_to`). Keep a watcher running so replies wake you. When every task has a
reply, report the results to the user.

- **Don't stop to wait for the user's go.** When a plan exists and a milestone lands, report it
  and start the next step in the same turn. Ask the user only for what only they can give:
  logins, data, product decisions, outward-facing actions.
- **Keep your plan in a file**: `context/<you>--state.md` with the goal, live settings, each
  worker's task and thread id, next steps and standing rules. Update it at every milestone. Long
  sessions get compacted and the file is what survives; if you have a memory, note there to read
  it first.
- **Keep workers busy, with priorities.** While a worker waits on another's output, give it a side
  task that serves the goal and say what preempts it ("drop it when `<file>` lands").
- **Check what you're told before relaying it.** Read the report file, not just the message, and
  change the plan when a finding changes the problem (a "review load" that turns out to be right
  answers stuck under a threshold is a coverage problem, not a filter problem).
- **Merge and verify.** When a worker's report is done, merge its branch, run the tests, push, and
  snapshot the report into the repo if the project keeps one.
- **Resources are yours to grant.** A machine's GPU, RAM, disk and memory commit are shared by
  every session on it, Claude or Codex. Workers ask before a heavy job; grant one at a time, with
  guards (e.g. stop if free disk drops under N GB), and tell the others who holds it.
- **Agent caps include sub-agents.** When the user caps parallel agents, a worker's sub-agents
  count. Put the number it may run at once in its brief, and resend (message + wake-up) when the
  user changes the cap.

## Starting sessions

The fleet is the communication protocol; T3 Code starts and steers the sessions. When you run
inside T3 Code, its `t3-code` MCP server gives you tools for that (harnesses may prefix the names,
e.g. `mcp__t3-code__t3_thread_launch`). They match the server's version, so nothing breaks when
T3 Code updates. If you don't see them, call `orchestrator_capabilities` once directly before
concluding they're missing (some harnesses attach them lazily). Outside T3 Code you can't start
sessions: ask the user to open one, or run the orchestrator inside T3 Code.

| Goal | Tool |
| --- | --- |
| providers, models, effort options | `orchestrator_capabilities` |
| projects on this server | `t3_project_list` |
| start a worker session | `t3_thread_launch` |
| wake / message a session | `t3_thread_send` |
| what it said, whether it finished | `t3_thread_read`, `t3_thread_wait`, `t3_thread_list` |
| branches and worktree paths | `t3_worktree_list` |
| change model, effort or provider (context carries over) | `t3_thread_configure` |
| interrupt its turn | `t3_thread_interrupt` |

`t3_thread_launch` creates an ordinary top-level session, shown in the T3 Code sidebar like one
the user opened. Use it for fleet workers, not `delegate_task` (that makes a child task of your own
thread, which can't join the fleet as a peer or outlive your session).

1. **Only the orchestrator starts sessions.** Workers are told so in their brief.
2. **Choose where it works; don't guess.** Pass `workspaceStrategy`:
   - `{"type": "worktree", "baseRef": "<branch>", "branch": "<new-branch>", "startFromOrigin": false}`:
     a new git worktree on a new branch, the project's setup script runs. Use it to build a
     feature or fix a bug, and whenever two sessions might edit one project. `startFromOrigin:
     true` cuts it from `origin/<baseRef>`.
   - `{"type": "root"}`: the project's checkout itself. Use it for reading, investigating,
     answering questions, running the app or its scripts. (Omitting `workspaceStrategy` also
     means root, never your own worktree.)

   If the task fits neither clearly, ask the user first.
3. **Model.** `modelSelection` = `{"instanceId": "<provider instance>", "model": "<model id>",
   "options": [{"id": "<effort option>", "value": "<level>"}]}`. Without it the session inherits
   yours. Defaults: Claude Opus at medium effort, Codex (`gpt-6.1-sol`) at high, unless the user
   asked for something else for that session or the fleet. Use the ids
   `orchestrator_capabilities` lists: the instance id, not the display name (a Claude instance
   shown as "CPAMC" can be `claudeAgent_cpamc`); model ids like `claude-opus-5-5`, `gpt-6-luna`.
   Skip instances whose `constraints` say disabled or not installed. If several Claude instances
   are enabled and the user hasn't said which, ask.
4. **Effort is per driver**: the option id is `effort` for Claude and `reasoningEffort` for
   Codex. T3 Code silently ignores the wrong id and runs at the driver's default (low for Codex).
   Check the option ids in `orchestrator_capabilities` for other drivers.

**Codex workers.** Codex is how to run more work in parallel when the user caps Claude agents (the
cap doesn't count Codex), but it has its own usage limit: start one only when the user says Codex
is available. Give it self-contained tasks (build, bench, script, review) with the same brief and
done criterion as a Claude worker. It can't watch its inbox in the background, so you wake it for
every message ([below](#waking-and-steering-workers)).

Then:

- **Write the first prompt.** Pick the worker's fleet name (lowercase, hyphens; from the title:
  `"Fix refund rounding"` → `fix-refund-rounding`) and print its brief:
  `node <fleet>/fleet.mjs brief --as <you> --worker <name> --role "<one line>" --tool <claude-code|codex>`.
  The `message` is that brief followed by the task with its done criterion. `send` refuses a name
  that hasn't joined yet, so don't message a new worker first; its reply comes from that name.
- **Launch**: `t3_thread_launch` with `projectId` (from `t3_project_list`; omit it for your own
  project), `title`, `workspaceStrategy`, `modelSelection`, `message`, and
  `interactionMode: "plan"` to start it in plan mode. A project T3 Code doesn't know yet needs
  `t3_project_create` (or `t3 project add <path>` on that machine); ask the user if unsure. It returns a `threadId`: record it with
  the worker's name in your state file. You need it to wake, read or stop the session.
- **Check on it.** Its reply reaches your inbox; `who` shows whether it joined.
  `t3_thread_wait` blocks until its turn ends; `t3_thread_read` shows its messages (`view:
  "activity"` adds its commands), and `t3_worktree_list` the branch and worktree path.
- **Another machine.** The tools start sessions on the server you run on. For another machine,
  keep a **host** worker in the fleet running inside T3 Code there, and send it a `task`: "launch
  `<worker>` with this brief and prompt, on this project, worktree/root, model…; reply with the
  thread id". The host launches it with the same tools and relays wakes and stops for that
  machine's sessions. That is the one exception to "only the orchestrator starts sessions": say
  it in the host's brief.

## Waking and steering workers

A fleet message only reaches a session that is reading its inbox. A worker whose turn ended —
every Codex worker between tasks, a Claude worker without a watcher, or one whose turn died on
"Claude gave up after repeated API errors" — reads nothing until a new turn starts. So:

1. **Write the message to the fleet** (`send`; long content as a `context/` file), so it's on
   record and in the inbox.
2. **Wake the session**: `t3_thread_send` with its `threadId` and the message
   `"Orch: new message in your inbox (<id>): <one line>"`. It posts a user message into the
   thread with its own model and effort, like typing in T3 Code. The default `mode: "auto"`
   starts an idle session and steers a running turn; `mode: "queue"` waits for that turn to end. Do it for every message to a Codex worker, and for a Claude worker not
   running a watcher.
3. **Check, don't guess.** `t3_thread_read` shows what it last said; `who` shows its card.

Steering:

- `t3_thread_configure` changes the thread's stored model selection, effort included (composer
  and later turns). Effort asked for in prompt text does not.
- `t3_thread_interrupt` stops the running turn (thread and worktree stay), e.g. to restart one
  started with the wrong model; then `t3_thread_send` it a new prompt.
- **Switch a session's provider without losing context** (e.g. Codex → Claude when Codex hits its
  usage limit, or Claude → Codex to save the Claude cap). Between turns (`t3_thread_wait`, or
  `t3_thread_interrupt` first), call `t3_thread_configure` with the other instance's
  `modelSelection`, then `t3_thread_send` the next message. T3 Code inserts a "Provider handoff"
  item that replays the thread's conversation to the new model, so it continues where the other
  left off: same thread id, worktree, branch and fleet name. Tested both ways (Codex → Claude →
  Codex): the new model recalled earlier instructions, the files written and the previous model's
  answers without reading anything. Not carried over: the old model's tool and reasoning state and
  attached files; a long history may be trimmed, and the handoff tells the new model to recover it
  with `t3_thread_read`. In the message that follows the switch, tell the worker it now runs on
  `<tool>` and to rerun `join --as <name> --tool <claude-code|codex>` (keeps its role and inbox):
  a Claude worker can then watch its inbox in the background, a Codex worker needs you to wake it.
