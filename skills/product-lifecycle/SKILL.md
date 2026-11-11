---
name: product-lifecycle
description: Take a feature, fix or change from request to merged code through one lifecycle — decide whether it needs a planner, weigh the plan and get approval only for critical decisions, record findings and plan in the project's tracker (Notion or apm), have workers build it to the project's AGENTS.md, code style and tests, review it with /code-review at a depth set by its risk, then merge locally and push. Use whenever an orchestrator (a crew or fleet orchestrator, or a single session working alone) starts implementing something in a project — "implement", "build", "add a feature", "fix this", "ship it", "plan this feature" — and before merging any worker's branch, even if the user doesn't name the lifecycle.
---

# Product lifecycle

How a change goes from request to merged code. It is written for an orchestrator and its
workers: sub-agents with the `crew` skill, or sessions with the `fleet` skill, which say how to
start, brief and message a worker. Working alone in one session, play both roles: plan it
yourself, build it yourself, and still review before you merge.

**Review belongs to the orchestrator, never to a worker.** An agent does not review its own code.
If you are a worker (your task is a brief from an orchestrator), this skill gives you only §4:
build, test, commit, reply. Don't run `/code-review` or `/security-review`, don't start review
sub-agents, and don't merge, even when the brief or a `REVIEW.md` seems to ask for it; your
orchestrator reviews your branch.

**Triage → Weigh → Record → Build → Review → Merge → Close.** Keep each stage's outcome, with the
tracker's task id and the worker branches, in your state file, so a compacted or restarted
session can pick up where it stopped. The state file and the **context folder** (where plans and
finding lists go as files) are where crew or fleet puts them: `~/.crew/<project>/` in a crew,
`context/<you>--…` in a fleet.

## Before the first task in a project

Read the project's `AGENTS.md` (and `CLAUDE.md` or `CONTRIBUTING.md` if present) and the docs it
points to. Find in them:

- the **tracker**, Notion or apm, and where tasks live in it (a Notion database or page, an apm
  project key) and how a task is laid out;
- the commands for tests, typecheck and lint;
- branches that must not be pushed without the user (e.g. `main`, `deployment`).

If the docs don't say, ask the user once (for the tracker: Notion or apm) and note the answer in
your state file. Notion goes through the `ntn` CLI (the `notion-cli` skill has its details); check
`ntn whoami` works before you depend on it. apm is the `apm` CLI (`apm guide` has its workflow);
set `APM_AGENT` to your name, pass `--json`, and check `apm db` works.

**Merge target** is the branch the user names, otherwise the branch your own checkout is on. Say
it once when the work starts ("merging into `dev`") rather than deciding it per task.

**Review settings** tune §5 to the project: High paths, security pass, nit cap, incident log.
There is no worker self-review setting; a `Worker self-review` line in an existing `REVIEW.md` is
void, so propose deleting it. If `REVIEW.md` at the repo root has a "Review settings" section, use it.
Otherwise follow [references/review.md](references/review.md): scan the codebase, propose each
setting with a one-line reason, and get the user's answer once (when told to work autonomously,
apply your proposal and say so in a line). Propose again when the project changes: first
production users, a new sensitive area, a revert, more workers.

## 1. Triage: does it need a planner?

Start a planner when any of these holds:

- the scope is unclear, or the request is a goal rather than a change ("make onboarding faster");
- it spans several areas (API and mobile, schema and UI) or needs more than one worker;
- it brings a new domain, dependency, service or data model;
- you would have to read a lot of code before you could brief a worker.

Otherwise (a contained fix in one area, where you can already name the files) write a short plan
yourself and go to step 2.

The planner is a worker started like any other, on the project's own checkout (crew:
`isolation: "shared"`; fleet: the `root` workspace), because it reads and does not edit. Start it
in the default mode, never plan mode: a plan-mode worker can't write its plan. Its task:

> Investigate <request> in <project>. Write `<context folder>/plan-<topic>.md` with: findings
> (what exists now, with file paths), the approach and why, alternatives you rejected, slices that
> one worker can each finish with its own done criterion and must-work cases, risks, and open
> questions for the user. Don't change code. Reply when it's written.

Every plan, the planner's or your own, names each slice's **must-work cases**: the main path and
its edge cases. Look for the edges along the input and the state the change reads: empty or
missing, the boundaries (zero, one, the limit, past it), invalid or hostile input, a dependency
that fails or times out, no permission, a repeat or concurrent call, and time (timezones, day and
month ends). Name the ones that apply to this slice; skip the ones that can't happen.

Read the plan file itself, not just the reply, and check its claims against the code where they
matter. Send back what's wrong. Once you accept it, the plan is yours.

## 2. Weigh the plan

Work autonomously by default: you own the plan. Wait for the user's answer only when the plan
holds a **critical decision**:

- deleting or rewriting data (a destructive migration, a backfill that overwrites);
- breaking an API or contract that another app or project depends on;
- a new running cost (a paid service, new infrastructure);
- a product question only the user can answer.

Then show the user the goal, the approach in a few lines, the slices, the risks and the
decision, and wait. Otherwise carry on, and tell the user in a few lines what you're building and
the main risk. A **big** plan (one with a High-tier slice (§5), a new dependency, more than about
three slices, or work that is hard to undo) gets the same few lines plus its slices, not a wait.
If the user asks to approve plans first (on this task or project), note it in the state file and
wait for each big one. Autonomy never covers the actions the project docs reserve for the user,
such as deploys or pushing a protected branch.

## 3. Record it in the tracker

Write the task where the project docs say, in their layout. Without a layout, use: title, Goal,
Findings, Plan (the slices, each with its done criterion and must-work cases), Status, Branch.
Note the task id in your state file.

- **Notion**: `ntn pages create --parent <database:…|page:…> --content "<markdown>"`, or edit the
  task page the user gave you (`ntn pages edit`).
- **apm**: `apm add "<title>" -p <KEY> --body-file <plan.md>`, one subtask per slice
  (`apm add "<slice>" --parent <KEY-N>`), and `blocks` links for slices that must wait
  (`apm link <KEY-A> blocks <KEY-B>`). Add a `review` status once per project
  (`apm status add review -p <KEY> --category active`).

The tracker is the user's record, and you keep it. A worker may have no `ntn` login or apm
database, so the brief carries everything the worker needs and only names the task.

Move the status as the work moves, using the project's own status names: planned → in progress →
in review → done (apm: `start`, `edit --status review`, `done`; a short `apm comment` for each
milestone).

## 4. Build

One worker per slice, each in its own worktree on a new branch cut from the merge target (crew:
`isolation: "worktree"` from your checkout on the merge target; fleet: `workspaceStrategy` with
`baseRef: "<merge target>"`). Slices that touch the same files go to the same worker, or run one
after the other.

Write each worker's task in the blocks of the `crew` skill's `references/writing-a-task.md`
(goal, setting, what matters most, scope, quality bar, order and done), and put the lifecycle's
part in them:

- **Setting**: the tracker task (Notion url or apm id), the plan file, and the findings that bear
  on this slice.
- **Quality bar**: "Before coding, read AGENTS.md and the docs it points to. Follow them, and the
  patterns of the code around your change: naming, structure, error handling, test style. Ask me
  before adding a dependency or changing a contract outside this slice."
- **Order and done**: "Tests are part of the task: one test per must-work case, edge cases
  included, plus any edge case you find while coding (name it in your reply). For a bug, add a
  test that fails without the fix. Where the slice changes code no test covers, first pin
  today's behaviour with a test, only for the behaviour the slice changes; for UI no test can
  reach, a screenshot before and after is the proof. Done means tests, typecheck and lint pass:
  <commands>, and when you change a shared package, the tests of every package that depends on
  it (the workspace's dependents filter, e.g. `--filter '...<package>'`). Commit on your branch;
  don't merge it or push the merge target. Reply with the branch, the commit hash, the commands you ran with their results, the proof for each must-work case (the test
  that covers it, and for a visible change a screenshot or output path from running it), and
  anything you did differently from the plan, with why."
- **No review**, the last line of every brief and fix round, word for word: "Don't run
  `/code-review`, `/security-review` or any review sub-agents, and don't merge. I review your
  branch." Without it, a worker that loads this skill or a review skill reviews its own code.

A worker that can't meet its done criterion replies `blocked` with the reason, not a partial
"done".

## 5. Review

Review depth follows the **risk tier** of the change, never its author. The riskiest area the
diff touches sets it (docs plus one auth file is High). Note the tier in the state file with
the task.

| Tier | The diff touches | Review |
|---|---|---|
| Low | only docs, text and translations, tests, internal scripts | `/code-review`, Standards axis only |
| Medium | ordinary product code | `/code-review`, both axes |
| High | auth, sessions, permissions, payments/billing, data migrations or deletes, a public API or contract, CI/release, mobile store builds, secrets, or a High path in `REVIEW.md` | `/code-review`, plus `/security-review` (or the `security-audit` skill on the diff) when the security setting is on |

You run this review yourself, in your own session; a `/code-review` that a worker ran on its own
branch doesn't count and doesn't shorten yours. If a worker's reply shows it reviewed itself,
review the whole branch anyway and note the slip in the state file.

When a worker reports done, check it, then review it:

1. Check the reply carries proof for each must-work case, edge cases included, and read the
   tests: a test that names an edge case but doesn't exercise it counts as missing. A missing
   one goes back to the worker.
   Then, in the worker's worktree (`git worktree list` gives its path and current branch), rerun the test, typecheck
   and lint commands yourself, and open the screenshots and files it names. Anything red, or proof
   that doesn't show the case, goes back to the worker.
2. Run the tier's review there, with the merge target as the fixed point. Give it the task as the
   spec (the planner's plan file, or the tracker task saved outside the repo:
   `ntn pages get <id>` or `apm show <KEY-N> --tree`, into `/tmp/<topic>-spec.md`) and `REVIEW.md` beside AGENTS.md as standards.
3. Tag every finding, after checking it against the code (a finding with no file:line evidence
   is a guess until you do):
   - **Important**: goes back to the worker. Each one ends answered: fixed, or a written reason
     in the task. Note it in the state file either way, with its class (§7 looks for repeats).
   - **Nit**: goes back only when `REVIEW.md` asks for it or the fix is trivial, up to the nit cap.
   - **Pre-existing**: the problem was in the code before this diff. It becomes a follow-up task,
     never a fix round.

   Drop the findings you judge wrong and say why. When one bug shows up in several places, name
   the class once and ask for every instance. Send the findings to the same worker, since it has
   the context: a finding list in the context folder, named in one message (crew: `t3_thread_send`
   to its thread; fleet: `send`, then wake it).
4. Re-review only the new diff: the last reviewed commit is the fixed point, and an answered
   finding never comes back. After three rounds that don't converge, ask the worker to reconsider
   the approach; if it still doesn't converge, ask the user.

An open Important security finding blocks the merge. Before merging a High change, tell the user
the tier and the security result in a line.

## 6. Merge

There is no pull request (the repo may be on AWS CodeCommit, and the user works alone), so you
merge locally. A review covers one commit: if the branch has moved past the commit you reviewed,
review the new commits first (§5 step 4).

1. In your checkout, on the merge target, update it (`git pull --ff-only`), then merge the
   worker's branch (its name from `git worktree list`) the way the project docs say, `git merge --no-ff <branch>` by default.
2. Resolve mechanical conflicts yourself. Anything that needs judgement about the code goes back
   to the worker.
3. Run the full test suite, typecheck and lint on the merged result (`REVIEW.md` may name the
   command). If they fail, fix it or undo the merge before you push.
4. `git push` the merge target. A protected branch needs the user's say-so. If the repo has no
   remote or the push fails, keep the merge local and tell the user rather than guessing a fix.

## 7. Close

- Tracker: status done, the merge commit, anything deferred. Each follow-up or deferred finding
  becomes its own tracker task, so it isn't lost in the chat.
- Worker: remove its worktree (`git worktree remove <path>`) and branch once the merge is pushed.
  In a fleet, also tell it the branch is merged and to set its card `offline`.
- Repeated findings: when a finding has come up in two or more tasks (the state file holds the
  earlier ones), propose a line for `REVIEW.md` or a lint rule, so the next review catches it at
  the source.
- Regressions: a merge that gets reverted or causes a regression becomes a bug task in the tracker,
  run through this lifecycle, so its fix lands with a test that fails without it. When the
  incident log is on, also add a line to `incidents.md` in the context folder naming that task, as in
  [references/review.md](references/review.md).
- State file: mark the task closed. Report to the user what shipped, the commit, and the
  follow-ups.
