# Refusals and what they mean

The CLI's messages are specific. Match the one you got rather than guessing at a cause.

## Getting started

**`agent-board: command not found`**

Either it is not installed, or its directory is not on the path of the shell you are
using. Non-interactive shells do not read the user's profile, so a binary they can run
themselves may still be invisible to you. Try
`export PATH="$HOME/.agent-board/bin:$PATH"` before installing anything.

**`No agent-board.json found in <dir>. Run \`agent-board init\` first.`**

Commands resolve workspaces relative to the config file in the current directory. Either
`init` here, or change to the directory that already has one.

## Migrations

**`Workspace "<id>" is up to date (database vN).` — but your migration did not run**

Its version number is at or below the highest already applied. `migrate` only applies
versions greater than the maximum in the ledger, so a file filling an earlier gap is
skipped without a warning. Renumber it above the current maximum. `inspect` shows what
has been applied.

**`Migration <file> was already applied with a different checksum.`**

The file changed after it was applied. Applied migrations are frozen — restore the
original contents and correct the schema in a new migration.

**`Forbidden statement matched /\bPRAGMA\b/i — not allowed in migrations.`**

Also fires for `ATTACH`, `DETACH`, `VACUUM`, `load_extension`. These reach past the
schema the runtime can reason about. Express the intent in DDL, or accept the default.

**`References protected namespace "_audit_*" — platform-owned tables.`**

The check is a substring scan over the whole file, so it fires on a *comment* mentioning
`_audit_`, `_auth_` or `_agentboard_` as readily as on a real reference. Rewrite the
comment without the underscores.

**`Migration file "<name>" does not match NNNN_name.sql`**

Four digits, an underscore, a name, `.sql`. For example `0003_add_orders_index.sql`.

**`Migration failed — restored snapshot #N.`**

Not an error to recover from — the workspace was already rolled back to its pre-migrate
state. The error printed after it is the real cause.

## Publishing

**`Refusing to publish: expected application version 0 but the workspace is at 1.`**

`--expect-version` guards against overwriting a change you did not see. Re-read the
current version with `inspect`, confirm the newer version is not something you need, and
publish against it.

**`failed validation with N error(s)`**

Each line names a path such as `pages[0] ("overview").components[1]`. An
`unknown property "…"` line means a typo — the message lists the allowed keys. See
`references/dsl.md`.

**A saved query fails during publish**

Gate 4 executes every saved query at `LIMIT 1`. A failure here means the specification
and the database disagree: a column was renamed, a table does not exist yet, or JSON
functions hit malformed data. Run the statement with `agent-board query <ws> "<sql>"` to
see the raw error, then fix the SQL or add the migration it needs.

## Queries

**`Query must be read-only — it must start with SELECT or WITH.`**

Writes go in migrations. There is no other write path.

**`Missing value for parameter(s): plan. Supply every declared parameter.`**

Pass `--param plan=<value>`. Every declared parameter is required, with no defaults.

**`Query does not declare parameter(s): bogus. Declared: plan.`**

The parameter name is not in the statement. Unknown names are refused rather than
ignored, because the driver would otherwise bind NULL and return plausible wrong rows.

**Results look short**

The default cap is 100 rows. `--limit` raises it; `--json` reports `truncated`. For
totals, aggregate in SQL rather than counting returned rows.

## Recovery

`inspect` lists snapshots. `restore <workspace> <seq>` rewinds to one. `export` writes
the whole workspace as a tarball — worth doing before anything irreversible.
