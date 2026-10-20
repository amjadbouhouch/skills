---
name: product-lifecycle
description: Take a feature, fix or change from request to merged code through one lifecycle — decide whether it needs a planner, weigh the plan and get approval when it's big, record findings and plan in the project's Notion task, have workers build it to the project's AGENTS.md, code style and tests, review it with /code-review, then merge locally and push. Use whenever an orchestrator (a fleet orchestrator, or a single session working alone) starts implementing something in a project — "implement", "build", "add a feature", "fix this", "ship it", "plan this feature" — and before merging any worker's branch, even if the user doesn't name the lifecycle.
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

## 1. Triage: does it need a planner?

Start a planner when any of these holds:

- the scope is unclear, or the request is a goal rather than a change ("make onboarding faster");
- it spans several areas (API and mobile, schema and UI) or needs more than one worker;
- it brings a new domain, dependency, service or data model;
- you would have to read a lot of code before you could brief a worker.

Otherwise (a contained fix in one area, where you can already name the files) write a short plan
yourself and go to step 2.

The planner is a fleet worker started like any other (fleet `references/orchestrating.md`), in
the `root` workspace and plan mode, because it reads and does not edit. Its task:

> Investigate <request> in <project>. Write `context/<planner>--plan-<topic>.md` with: findings
> (what exists now, with file paths), the approach and why, alternatives you rejected, slices that
> one worker can each finish with its own done criterion, risks, and open questions for the user.
> Don't change code. Reply when it's written.

Read the plan file itself, not just the reply, and check its claims against the code where they
matter. Send back what's wrong. Once you accept it, the plan is yours.

## 2. Weigh the plan

Decide whether the user approves before anything is built. A **big** plan goes to the user and
you wait for their answer, unless they told you to work autonomously (on this task or project;
note it in the state file). A plan is big when any of these holds:

- a schema or data migration, or anything that deletes or rewrites data;
- a change to an API or contract that another app or project depends on;
- a new dependency, service, piece of infrastructure, or running cost;
- auth, payments, permissions or security;
- more than about three slices, or work that is hard to undo;
- open questions only the user can answer.

Show the user the goal, the approach in a few lines, the slices, the risks and the questions.
For a small plan, carry on and tell the user in a line what you're doing. Working autonomously
doesn't cover the actions the project docs reserve for the user, such as deploys or pushing a
protected branch.

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
the same files go to the same worker, or run one after the other. Add this to the fleet brief:

> Task: <slice>. Notion: <url>. <Goal, the findings that matter, the done criterion.>
> Before coding, read AGENTS.md and the docs it points to. Follow them, and the patterns of the
> code around your change: naming, structure, error handling, test style. Ask me before adding a
> dependency or changing a contract outside this slice.
> Tests are part of the task: cover the new behaviour, and for a bug add a test that fails
> without the fix. Done means tests, typecheck and lint pass: <commands>.
> Commit on your branch; don't merge it or push the merge target. Reply with the branch, the
> commit hash, the commands you ran with their results, and anything you did differently from
> the plan, with why.

A worker that can't meet its done criterion replies `blocked` with the reason, not a partial
"done".

## 5. Review

When a worker reports done, check it, then review it:

1. In the worker's worktree (`t3_worktree_list` gives the path), rerun the test, typecheck and
   lint commands yourself. Anything red goes back to the worker.
2. Run `/code-review` there, with the merge target as the fixed point and the task as the spec:
   the planner's plan file, or the Notion page saved outside the repo
   (`ntn pages get <id> > /tmp/<topic>-spec.md`).
3. Send the findings you agree with back to the same worker, since it has the context: one
   message naming a context file that lists them, then wake it. Drop the ones you judge wrong and
   say why. Smells flagged as judgement calls get fixed when they're cheap or the project's
   standards ask for it.
4. Review again after the fixes. After three rounds that don't converge, stop and ask the user.

## 6. Merge

There is no pull request (the repo may be on AWS CodeCommit, and the user works alone), so you
merge locally:

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
- State file: mark the task closed. Report to the user what shipped, the commit, and the
  follow-ups.
