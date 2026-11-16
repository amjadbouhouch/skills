# Council

Run a council only when the user says "council". It adds outside opinions to your own review; it
never replaces it. In product-lifecycle work you still run the tier's `/code-review` (§5) and
check each worker's proof. The council is one more input.

## Before you call it

Give the council the current implementation. Send known findings, red checks and open fix rounds
to the worker first, and wait for its fixes. Don't save known fixes until the council reports.
If the user wants to drop the implementation and explore new ideas, skip fixes to the code you
replace.

## Members

One strong model from each enabled provider, at high effort:

| Seat | `providerInstanceId` | `model` | `options` |
|---|---|---|---|
| Claude | your own instance (`inheritedProviderInstanceId` from `orchestrator_capabilities`) | `claude-opus-5-5` | `effort: high` |
| Codex | `codex` | `gpt-6.1-sol` | `reasoningEffort: high` |

If the user names members, use those. If a seat's instance is disabled or missing, run with the
seats you have, and name the missing seat in your report. Never fill a seat with a second model
from a provider that already has one.

Council delegates review; they aren't workers and don't count toward the 3-worker cap.

## Starting the delegates

Start every seat in parallel with `delegate_task`, `mode: "async"`, `isolation: "shared"`,
`title: council-<seat>-<topic>` (`council-codex-refund-rounding`). Each brief carries:

- The request, and the spec (the plan file or the tracker task saved to `/tmp/<topic>-spec.md`).
- What to review: the worker's worktree path and branch from `git worktree list`, and the fixed
  point (the merge target, or the last reviewed commit in a later round).
- **Read-only**: "Don't edit, commit or merge anything. Report findings only."
- What to return: findings with file:line evidence, each tagged Important or Nit; a score out
  of 10; and one line, "satisfied: yes" or "satisfied: no".

Record each delegate's seat, `taskId` and `childThreadId` in the state file.

## While they run

Don't wait idle. When a result arrives, check its findings against the code at once, and decide
which to accept while the other seats run. Tag them as in product-lifecycle §5: Important, Nit,
Pre-existing. Drop the findings you judge wrong and say why.

Don't send a fix round to the worker while a delegate still reviews its worktree. Send one finding
list after the last seat reports, with your own `/code-review` findings in it.

## Rounds

One full review pass by every seat is one round. After the worker fixes, a fresh review is a new
round: a new `delegate_task` for each seat, never a `t3_thread_send`. Give it the last reviewed
commit as the fixed point, and the findings already answered so they don't come back.

Stop when every seat says "satisfied: yes". After 3 rounds that don't converge, show the user the
open disagreements and ask.

Fight scope creep. A finding outside the task's done criterion becomes a follow-up task in the
tracker, never a fix round.

## Recording the result

Put the score table in the tracker task (Notion or apm), next to its findings and plan:

```markdown
## Council review

Rounds: 2

| Delegate | Round 1 | Round 2 |
| --- | --- | --- |
| Claude Opus 5.5 | 7/10 | 9/10 |
| Codex GPT-6.1 Sol | 8/10 | 10/10 |
```

If a delegate gives no score, write `no score`. Never invent one. Name a missing seat under the
table. Show the same table in your report to the user, with the useful findings, the
disagreements and the next steps.
