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

`spawn.mjs` starts a T3 Code session, on this machine or another, and sends it its first prompt.
It shows up in the T3 Code sidebar like one the user opened, and runs in full-access mode.
`node <fleet>/spawn.mjs help` is the reference for every option and default; the rules below are
what it can't decide for you.

1. **Only the orchestrator starts sessions.** `spawn.mjs new` refuses unless `--as` names the
   fleet's orchestrator.
2. **Choose where it works; `spawn.mjs` won't guess.**
   - `--worktree`: new git worktree on a new branch, cut from the checkout's current branch
     (`--base <branch>`, or `--from-origin` for `origin/<base>`); the project's setup script runs.
     Use it to build a feature or fix a bug, and whenever two sessions might edit one project.
   - `--checkout`: the project's checkout itself. Use it for reading, investigating, answering
     questions, running the app or its scripts, or continuing on the branch already checked out.

   If the task fits neither clearly, ask the user first.
3. **Keep the defaults** (in `spawn.mjs help`: Claude Opus at medium effort; `--provider codex`
   gives Codex at high effort). Pass `--provider`, `--model` or `--effort` only when the user asked
   for it, for that session or the fleet. Use model ids, not display names: `gpt-6-luna` not
   `GPT-6-Luna`, `claude-sonnet-5-5`, `claude-opus-5-5[1m]` for 1M context. Which models exist
   depends on the user's T3 Code settings.

**Codex workers.** Codex is how to run more work in parallel when the user caps Claude agents (the
cap doesn't count Codex), but it has its own usage limit: start one only when the user says Codex
is available. Give it self-contained tasks (build, bench, script, review) with the same brief and
done criterion as a Claude worker. It can't start sub-agents or watch its inbox in the background,
so you wake it for every message ([below](#waking-and-steering-workers)).

**Providers** are T3 Code instances from the server's settings; `spawn.mjs providers` lists them.
Without `--provider`, `spawn.mjs` uses the one enabled Claude instance, whatever its id. If there
are none or several, it stops and lists them: ask the user which, then pass `--provider <id or
display name>`. A Claude instance defaults to Opus; any other instance needs `--model` unless it
is the server's default instance. Bad providers fail
before anything is created, and a start that fails later removes its worktree and branch.

**Effort is per driver** (`effort` for Claude, `reasoningEffort` for Codex). T3 Code silently
ignores the wrong key and falls back to the driver's default (low for Codex). `spawn.mjs` picks
the right one, but look at T3 Code's composer after starting sessions to confirm.

Then:

- **Find the project.** `spawn.mjs projects` lists the server's projects; a session can only start
  in one T3 Code already knows on that machine. If it's missing, ask the user, or run
  `t3 project add <path>` there.
- **Start a worker**:
  `spawn.mjs new --as <you> --project <p> --worktree --title "<short>" --prompt "<task>"`.
  `spawn.mjs` prepends a brief telling it to join, read `PROTOCOL.md`, reply to you when done, and
  never start sessions. The prompt *is* its first task: `send` refuses a name that hasn't joined
  yet, so don't message a new worker first, and match its reply by sender rather than by
  `reply_to`. Its fleet name comes from the title (`"Fix refund rounding"` →
  `fix-refund-rounding`) unless you pass `--name`; `new` prints it and the thread id. Put the done
  criterion in the prompt, as in a task message. `--plan` starts it in plan mode. `--no-fleet` is
  only for a one-off question you'll read with `spawn.mjs read`.
- **Another machine**: `--server <name>` from `~/.config/fleet/servers.json` (see `help`). The
  user sets it up once: on that machine, start T3 Code reachable (`t3 serve --host <tailnet-ip>`
  or `--tailscale-serve`) and issue a token with
  `t3 auth session issue --ttl 30d --label orch --token-only`. Without `--server`, `spawn.mjs` uses
  the local server and a short-lived token from the `t3` CLI. Needs Node ≥ 22.
- **Check on it.** Its reply reaches your inbox; `who` shows whether it joined. `spawn.mjs threads`
  shows each session's branch (T3 Code may rename a new `t3code/<random>` branch, so read it from
  there, not from `new`'s output), and `spawn.mjs read <thread-id>` prints its latest messages.

## Waking and steering workers

A fleet message only reaches a session that is reading its inbox. A worker whose turn ended —
every Codex worker between tasks, a Claude worker without a watcher, or one whose turn died on
"Claude gave up after repeated API errors" — reads nothing until a new turn starts. So:

1. **Write the message to the fleet** (`send`; long content as a `context/` file), so it's on
   record and in the inbox.
2. **Wake the session**: `spawn.mjs send <thread-id> --prompt "Orch: new message in your inbox
   (<id>): <one line>"`. This posts a user message into the thread with its own model and effort,
   like typing in T3 Code. Do it for every message to a Codex worker, and for a Claude worker not
   running a watcher.
3. **Check, don't guess.** `spawn.mjs read <thread-id> --last 2` shows what it last said; `who`
   shows its card.

Steering:

- `spawn.mjs effort <thread-id> <level>` changes the stored effort (composer and later turns);
  `--effort` on `send` stores it too. Effort asked for in prompt text does not.
- `spawn.mjs stop <thread-id>` interrupts the turn and stops the session (thread and worktree
  stay), e.g. to restart one started with the wrong model. `--turn-only` keeps the session and its
  background jobs.
