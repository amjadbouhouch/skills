# Writing a task

A task is the brief a capable peer works from alone, so it carries intent: what to achieve and
what matters, leaving the how to the worker. The worker starts with no history of yours: the
brief is all it knows. Write it as prose, one short paragraph per block, in this order:

1. **Goal.** The outcome in a sentence or two, told from the user's side (what they see or can
   do), anchored to a reference the worker can look at: a mockup, an existing screen, a product.
2. **Setting.** Repo and branch, which slice of which plan, where the spec lives, who builds what
   in parallel and the contract between you. A context file holds the detail; this paragraph is
   enough to start.
3. **What matters most**, and why. The one thing to protect when trade-offs come up; it is what
   lets the worker decide without asking.
4. **Scope.** What's in, what's out, and the cases that must work, named; they double as the
   acceptance tests.
5. **Quality bar.** How the worker proves its own work: the tests, and using what it built the
   way the user will (the flow in the running app, a screenshot beside the mockup, the output
   file opened, a benchmark), with the tools it has for it.
6. **Order and done.** What comes first, the done criterion with its commands, where to commit,
   and the reply: proof for each must-work case that you can check yourself (command output,
   test names, screenshot or file paths). A "done" without its proof goes back to the worker.

When a context file is the spec, the brief still states the goal, what matters most and done in a
few lines, and points to the file for the rest. A follow-up to a worker already on the job uses
the same blocks, as short as its context allows.

A full first brief, one paragraph per block:

> Let shop owners export their orders to CSV from the Orders page, so they can reconcile with
> their accountant without copying rows by hand. The button and its menu follow the Figma frame
> "Orders / Export" linked in the plan.
>
> This is slice B of `~/.crew/shop/plan-csv-export.md`: read its decisions and slice B first.
> Work in `apps/web`. Another worker is building `GET /orders/export?from&to&status` in parallel,
> returning `text/csv`; build against a stub in `apps/web/src/test/handlers.ts`, and I'll tell
> you when it's merged.
>
> What matters most is that the file opens cleanly in Excel and Numbers: amounts as plain numbers,
> ISO dates, UTF-8 with a BOM so accented customer names survive. A polished button that downloads
> a broken file is a failed task.
>
> In scope: the export button, the date and status filters it takes from the list, the download,
> and an error toast. Out of scope, as follow-ups: scheduled exports and choosing columns. Must
> work: a filtered list exports only its rows; an empty result downloads a header-only file; a
> failed request shows the toast and keeps the filters.
>
> Prove it: vitest for those three cases, then download a file from the stub, open it in a
> spreadsheet and compare it with the sample in the plan. Follow AGENTS.md and the patterns of the
> code around your change; ask me before adding a dependency.
>
> Start with the download path, then the UI. Done means `pnpm --filter web test`, `typecheck` and
> `lint` pass. Commit on your branch; don't merge or push. Reply with the commit hash, the
> commands with their results, the test that covers each must-work case, the downloaded file's
> path with a screenshot of it opened, and anything you did differently from the plan, with why.

A short one, when an approved context file is the spec:

> Make new conversation titles come out in the user's language instead of always English, so a
> French user's sidebar reads in French.
>
> The plan is approved and is the spec: read `~/.crew/chat/titles-build.md` in full and build it,
> with no plan step. What matters most is that existing titles stay as they are; only new
> conversations get localized titles. Done means the plan's tests pass along with `pnpm test`,
> typecheck and lint. Reply with the commit hash, the command results, and the titles generated
> for one French and one English conversation, with an existing title shown unchanged. Ask me
> only if the plan proves wrong in the code.
