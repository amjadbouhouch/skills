# Review settings, `REVIEW.md` and the incident log

## Proposing the settings

Before the first task in a project, scan the codebase:

- tests, CI, lint and typecheck: do they exist, and do they run?
- sensitive areas (auth, sessions, payments, permissions, PII, migrations, a public API, mobile
  store releases), with their paths;
- production users or not (ask if the docs don't say);
- a solo session or a fleet with workers;
- review findings that the docs or memory already show repeating.

Then propose the settings to the user in one table, each with a one-line reason drawn from the
scan ("Security pass on High: on, because `src/auth/` and `src/billing/` exist"; "Incident log:
off, no production users yet"). Start from these defaults:

| Setting | Default |
|---|---|
| High paths | the sensitive paths the scan found |
| Security pass on High | on if sensitive areas exist, else off |
| `REVIEW.md` | propose it; commit it only with the user's OK |
| Worker self-review | on in a fleet, off for a solo session (§5 already covers it) |
| Nit cap | 3 per review |
| Incident log | off; propose it once there are production users or a first revert |

Risk tiers and the convergence rules in §5 are always on: they route the review and cut rounds,
so they cost nothing to keep.

Save the answer in `REVIEW.md` under "Review settings". If the user wants no repo file, save it
in your state file.

## Shape of a `REVIEW.md`

Short, at the repo root, read by both `/code-review` axes:

```markdown
# Review

## Review settings
- Security pass on High: on
- Worker self-review: on
- Nit cap: 3
- Incident log: off

## High paths
- src/auth/
- db/migrations/

## Skip
- generated/

## What broken means here
- Docs: a doc that lies about the code.
- Config: a value that misroutes requests or environments.
- Migrations: a step that loses data or can't run twice.

## Findings
- Every finding cites file:line as evidence, not a guess from a name.
- At most <nit cap> nits per review.
- The report opens with a count per severity: Important, Nit, Pre-existing.

## Checked every time
- <one line per finding that has repeated across tasks>
```

The last section grows from §7 Close: each finding seen in two or more tasks becomes a line
there, or a lint rule when a tool can enforce it.

## Incident log

One line per incident in `context/<you>--incidents.md`:

```text
<date> | <task> | <merge commit> | what broke | layer that should have caught it (tests, self-review, /code-review, security pass, user)
```

When the review skills or `REVIEW.md` change, re-run the review on the logged commits as a quick
check that it now catches them. Keep it a log, without scoring.
