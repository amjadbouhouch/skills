---
name: product-lifecycle
description: Take a feature, fix or change from request to merged code through one lifecycle — decide whether it needs a planner, weigh the plan and get approval only for critical decisions, record findings and plan in the project's Notion task, have workers build it to the project's AGENTS.md, code style and tests, review it with /code-review at a depth set by its risk, then merge locally and push. Use whenever an orchestrator (a fleet orchestrator, or a single session working alone) starts implementing something in a project — "implement", "build", "add a feature", "fix this", "ship it", "plan this feature" — and before merging any worker's branch, even if the user doesn't name the lifecycle.
---

# Product lifecycle

How a change goes from request to merged code. It is written for a fleet orchestrator and its
workers (see the `fleet` skill). Working alone in one session, play both roles: plan it
yourself, build it yourself, and still review before you merge.

**Triage → Weigh → Record → Build → Review → Merge → Close.** Keep each stage's outcome, with the
Notion task id and the worker branches, in your state file (`context/<you>--state.md` in a fleet),
so a compacted or restarted session can pick up where it stopped.

## Before the first task in a project

Read the project's `AGENTS.md` (and `CLAUDE.md` or `CONTRIBUTING.md` if present) and the docs it
points to. Find in them:

- where tasks live in Notion (database or page) and how a task page is laid out;
- the commands for tests, typecheck and lint;
- branches that must not be pushed without the user (e.g. `main`, `deployment`).

If the docs don't say, ask the user once and note the answer in your state file. Notion goes
through the `ntn` CLI (the `notion-cli` skill has its details); check `ntn whoami` works before
you depend on it.

**Merge target** is the branch the user names, otherwise the branch your own checkout is on. Say
it once when the work starts ("merging into `dev`") rather than deciding it per task.

**Review settings** tune §5 to the project: High paths, security pass, worker self-review, nit
cap, incident log. If `REVIEW.md` at the repo root has a "Review settings" section, use it.
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

The planner is a fleet worker started like any other (fleet `references/orchestrating.md`), in
the `root` workspace, because it reads and does not edit. Start it in the default mode, never
plan mode: a plan-mode session can't run fleet commands, so its plan never reaches you. Its task:

> Investigate <request> in <project>. Write `context/<planner>--plan-<topic>.md` with: findings
> (what exists now, with file paths), the approach and why, alternatives you rejected, slices that
> one worker can each finish with its own done criterion, risks, and open questions for the user.
> Don't change code. Reply when it's written.

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

## 3. Record it in Notion

Write the task where the project docs say, in their layout. Without a layout, use: title, Goal,
Findings, Plan (the slices, each with its done criterion), Status, Branch. Create it with
`ntn pages create --parent <database:…|page:…> --content "<markdown>"`, or edit the task page
the user gave you (`ntn pages edit`). Note the page id in your state file.

Notion is the user's record. A worker on another machine may have no `ntn` login, so the brief
carries everything the worker needs and only links the page.

Move the status as the work moves, using the project's own status names: planned → in progress →
in review → done.

## 4. Build

One worker per slice, each in its own worktree on a new branch cut from the merge target
(`workspaceStrategy: {"type": "worktree", "baseRef": "<merge target>", ...}`). Slices that touch
the same files go to the same worker, or run one after the other.

Write each worker's task in the blocks of fleet `references/orchestrating.md` → "Writing a task"
(goal, setting, what matters most, scope, quality bar, order and done), and put the lifecycle's
part in them:

- **Setting**: the Notion task url, the plan file, and the findings that bear on this slice.
- **Quality bar**: "Before coding, read AGENTS.md and the docs it points to. Follow them, and the
  patterns of the code around your change: naming, structure, error handling, test style. Ask me
  before adding a dependency or changing a contract outside this slice."
- **Order and done**: "Tests are part of the task: cover the new behaviour, and for a bug add a
  test that fails without the fix. Done means tests, typecheck and lint pass: <commands>. Commit
  on your branch; don't merge it or push the merge target. Reply with the branch, the commit
  hash, the commands you ran with their results, the proof for each must-work case (the test
  that covers it, and for a visible change a screenshot or output path from running it), and
  anything you did differently from the plan, with why."
- **Self-review** (when the setting is on; default on in a fleet), appended to order and done:
  "Before you reply, run `/code-review` on your branch with <merge target> as the fixed point
  <and `/security-review`, on a High slice>. Fix what you agree with, and list what you left and
  why."

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

When a worker reports done, check it, then review it:

1. Check the reply carries proof for each must-work case; a missing one goes back to the worker.
   Then, in the worker's worktree (`t3_worktree_list` gives the path), rerun the test, typecheck
   and lint commands yourself, and open the screenshots and files it names. Anything red, or proof
   that doesn't show the case, goes back to the worker.
2. Run the tier's review there, with the merge target as the fixed point. Give it the task as the
   spec (the planner's plan file, or the Notion page saved outside the repo:
   `ntn pages get <id> > /tmp/<topic>-spec.md`) and `REVIEW.md` beside AGENTS.md as standards.
3. Tag every finding, after checking it against the code (a finding with no file:line evidence
   is a guess until you do):
   - **Important**: goes back to the worker. Each one ends answered: fixed, or a written reason
     in the task. Note it in the state file either way, with its class (§7 looks for repeats).
   - **Nit**: goes back only when `REVIEW.md` asks for it or the fix is trivial, up to the nit cap.
   - **Pre-existing**: the problem was in the code before this diff. It becomes a follow-up task,
     never a fix round.

   Drop the findings you judge wrong and say why. When one bug shows up in several places, name
   the class once and ask for every instance. Send the findings to the same worker, since it has
   the context: one message naming a context file that lists them, then wake it.
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
   worker's branch the way the project docs say, `git merge --no-ff <branch>` by default.
2. Resolve mechanical conflicts yourself. Anything that needs judgement about the code goes back
   to the worker.
3. Run tests, typecheck and lint on the merged result. If they fail, fix it or undo the merge
   before you push.
4. `git push` the merge target. A protected branch needs the user's say-so. If the repo has no
   remote or the push fails, keep the merge local and tell the user rather than guessing a fix.

## 7. Close

- Notion: status done, the merge commit, anything deferred. Each follow-up or deferred finding
  becomes its own Notion task, so it isn't lost in the chat.
- Worker: tell it the branch is merged and to set its card `offline`. Remove its worktree
  (`git worktree remove <path>`) and branch once the merge is pushed.
- Repeated findings: when a finding has come up in two or more tasks (the state file holds the
  earlier ones), propose a line for `REVIEW.md` or a lint rule, so the next review catches it at
  the source.
- Incidents (when the incident log is on): a merge that gets reverted or causes a regression gets
  a line in `context/<you>--incidents.md`, as in [references/review.md](references/review.md).
- State file: mark the task closed. Report to the user what shipped, the commit, and the
  follow-ups.
