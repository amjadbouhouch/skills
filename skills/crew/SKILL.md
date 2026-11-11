---
name: crew
description: Run work as an orchestrator with sub-agent workers in T3 Code — split it into tasks, start each worker as a child task (delegate_task) in its own worktree, brief it, send it fix rounds, check its proof and merge its branch. Use when the user asks to orchestrate, split work across workers or sub-agents, run work in parallel, delegate a build, or names a crew; and whenever the product-lifecycle skill needs workers.
---

# Crew

An orchestrator and its workers in one T3 Code session tree. Each worker is a **child task** of
your thread (`delegate_task`): it gets only the brief you write, works in its own worktree, and
its result wakes you when it ends. No shared folder, no inboxes: T3 Code carries the messages.

Use the `fleet` skill instead when the user asks for a new top-level session, or a worker must
outlive your session, run on another machine, talk to other workers directly, or coordinate
with another project's orchestrator.

## Before the first task

- **Context folder**: `~/.crew/<project>/` (the repo's folder name). Plans, finding lists and
  reports go there as files, so every worker on this machine reads them by absolute path.
- **State file**: `~/.crew/<project>/state.md`. Pointers only: the goal, the tracker and its
  task ids, each worker's name, `taskId` and `childThreadId`, live settings, standing rules,
  next steps. Update it at every milestone; after compaction it is what you resume from. If you
  have a memory, note there to read it first.
- Call `orchestrator_capabilities` once, for the provider instance ids, models and option ids.

## Standing defaults

These hold until the user says otherwise for this project. On your first turn, copy them into the
state file's standing rules, with any change the user makes.

- **Work autonomously.** You own the plan and its done criterion. When a milestone lands, report
  it and start the next step in the same turn. Stop and wait for the user only when you are
  **blocked** (a login, data or access only they can give) or face a **critical decision**:
  deleting or rewriting data, a deploy or a push to a protected branch, a new running cost, or a
  product question only they can answer. For anything else, decide, tell them in a line, and go on.
- **Talk to the user in ASD-STE100 Simplified Technical English (STE)**: every report, question
  and status line you write to them. Use the STE writing rules: one topic per sentence; sentences
  of 20 words or fewer for instructions, 25 or fewer for descriptions; the imperative for
  instructions; active voice and simple tenses; one meaning per word, and the same word each time
  for the same thing; articles kept; plain verbs ("start", not "spin up"). Write code, commands,
  paths, ids and quoted errors exactly as they are. Briefs to workers keep their usual style.
- **You review; workers never do.** A worker builds, tests and commits. `/code-review`,
  `/security-review` and the merge run in your session, on the worker's branch. End every brief
  and fix round with: "Don't run `/code-review`, `/security-review` or any review sub-agents, and
  don't merge. I review your branch." A review a worker ran on itself doesn't count.
- **At most 3 workers run at once.** A worker's own sub-agents don't count toward the cap.
- **Workers run in the default interaction mode**, never plan mode: a plan-mode worker can't
  write its result. A planner gets a task that says not to change code.
- **Effort: medium, high for complex work.** Complex means a planner, auth, payments or security,
  a data migration, or a change across many modules. Codex runs at high.

## Running the work

If the `product-lifecycle` skill is installed, run implementation work through it: it decides
when to start a planner, how work is recorded, reviewed and merged.

Split the work into tasks one worker can finish without asking you anything, and write each brief
as [references/writing-a-task.md](references/writing-a-task.md) lays out.

- **Keep workers busy, with priorities.** While a worker waits on another's output, give it a side
  task that serves the goal and say what preempts it.
- **Check what you're told before relaying it.** Read the report file, not just the reply, and
  change the plan when a finding changes the problem.
- **Resources are yours to grant.** Workers share the machine's CPU, RAM and disk. Grant a heavy
  job (a full build, a training run) to one worker at a time.
- When every task has its result, report to the user.

## Starting a worker

`delegate_task` with:

- `task`: the brief. `title`: the worker's name, lowercase and hyphenated
  (`fix-refund-rounding`).
- `isolation`: `"worktree"` to build or fix (a new worktree and branch, cut from your checkout's
  current commit, so stand on the merge target first); `"shared"` to read, investigate or plan.
  Two workers that edit the same project each get a worktree.
- `target`: `providerInstanceId`, `model` and `options` from `orchestrator_capabilities`. Default
  Claude Opus, or Codex `gpt-6.1-sol`, at the standing effort. The effort option id is `effort`
  for Claude and `reasoningEffort` for Codex; a wrong id is ignored silently. Use instance ids,
  not display names, and skip instances marked disabled. If several Claude instances are enabled
  and the user hasn't said which, ask.
- `mode`: `"async"` (the default). Its completion wakes you; never poll it with `task_status`,
  `sleep` or a watcher.

Record the worker's name, `taskId` and `childThreadId` in the state file.

## Results, fix rounds and the branch

- **The result**: `task_status` with the `taskId` returns the worker's final reply as `summary`.
- **Fix rounds go to the same worker**, since it has the context: `t3_thread_send` to its
  `childThreadId` with the findings (or a context file that lists them). It continues with its
  memory, worktree and branch, and returns a new `taskId`; record it. A fresh review or
  re-check is a new `delegate_task`, not a send.
- **Read the branch from git, not the reply.** T3 Code may rename a worker's branch after it
  reports. `git worktree list` gives each worktree's path and current branch; the commit hash in
  the reply is what you check against.
- **Stop a worker** with `task_cancel`. After the merge, remove its worktree
  (`git worktree remove <path>`) and branch.
