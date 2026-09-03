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

## Writing rows

**`An unbounded update would rewrite "items". Narrow it with --where <column><op><value>.`**

`update` and `delete` refuse without a filter. If you genuinely mean every row, say so
explicitly — `--where id!=@null` matches all of them, and the receipt and row cap still
apply.

**`The rows matching this update changed since the preview (receipt X, now Y).`**

Something wrote to the table between your preview and your apply, or you changed the
`--set` values. The receipt covers both. Re-run the preview and apply the new receipt.

**`This delete affects 1200 rows, beyond the 1000 row cap.`**

Narrow the filter, or pass `--force` if that really is the intent.

**`"--apply" does not apply to \`rows insert\`.`**

Inserts write directly, so there is nothing to confirm. A flag that does not belong to
the subcommand is refused rather than ignored, because ignoring it would confirm a
belief about what the command did.

**`Row 3: "price" is INTEGER but received "1,200", which is not a number.`**

SQLite would store that as text and every later `SUM()` over the column would be wrong.
Strip separators and units in the script that produces the JSON.

**`Insert failed: UNIQUE constraint failed: items.id`**

The row already exists. If you are reloading a file that gets regenerated, that is what
`rows upsert --on-conflict <col>` is for — it replaces what is already there instead of
failing. For a one-off collision, filter for it and `rows update`.

**`Upsert needs --on-conflict <column>[,<column>] naming the columns that identify a row.`**

Without it there is no way to tell an update from a duplicate. Name the column or columns
that identify a row — usually the primary key, or whatever carries the UNIQUE index.

**`Row 3 is missing "id", which identifies the row.`**

Every row in an upsert batch must carry the conflict columns; a row without them cannot
be matched against what exists. Fix it in the script that produced the JSON.

**`Insert failed: NOT NULL constraint failed: items.name`**

The column has no default and no value was supplied.

**A generated id you cannot find**

`rows insert` reports only a count unless you pass `--returning`. With a random UUID
default there is nothing to query back by afterwards, so ask for it at insert time.

## Publishing

**`Refusing to publish: expected application version 0 but the workspace is at 1.`**

`--expect-version` guards against overwriting a change you did not see. Re-read the
current version with `inspect`, confirm the newer version is not something you need, and
publish against it.

**`"filter" requires "targets".` / `"targets" must be a non-empty array — a filter that drives nothing.`**

A `filter` component has to name what it drives. Add `targets: [{ component: "<id>" }]`,
or `{ component: "<id>", parameter: "<name>" }` to bind one of that query's parameters.
The target must be another component on the same page that reads data.

**`targets[0]: "component" must name a component on this page. Available: …`**

The id is misspelled, or the component lives on a different page. Filters drive only
their own page. `a filter cannot target itself` and `"<id>" reads no data, so it cannot
be filtered` are the neighbouring cases.

**`targets[0]: "orders_by_plan" does not declare parameter "plan".`**

The target's saved query has no `:plan` in its SQL, or it is not in that query's
`parameters`. The binding is checked at validation precisely so a rename shows up here
rather than as an empty table in the browser.

**`failed validation with N error(s)`**

Each line names a path such as `pages[0] ("overview").components[1]`. An
`unknown property "…"` line means a typo — the message lists the allowed keys. See
`references/dsl.md`.

**A saved query fails during publish**

Gate 4 executes every saved query at `LIMIT 1`. A failure here means the specification
and the database disagree: a column was renamed, a table does not exist yet, or JSON
functions hit malformed data. Run the statement with `agent-board query <ws> "<sql>"` to
see the raw error, then fix the SQL or add the migration it needs.

## Serving

**`--cors will not accept "*".`**

`start` configures no authorization hook, so every workspace is served without
restriction and a wildcard would let any page the user visits read all of them. Name the
origins, or serve the page with `start --static <dir>` and skip CORS entirely.

**`Directory not found: <path>`**

`--static` resolves its argument before binding the port, so a typo fails immediately
rather than serving 404s. Pass a directory that exists.

**`{"error":"query_not_found","message":"Saved query \"x\" is not published."}`**

The server reads statement text only from the published specification, so a query you
added to the file but did not publish does not exist. Publish, then retry.

**`{"error":"not_found"}` for a page you expected to serve**

Static files are tried only after the API routes, and only for `GET`/`HEAD`. Check the
file is under the `--static` directory — paths that resolve outside it are refused —
and that `/` maps to an `index.html`. `references/http.md` lists every route.

## Queries

**`Query must be read-only — it must start with SELECT or WITH.`**

`query` reads; it never writes. Change data with `rows insert|upsert|update|delete`.

**`Missing value for parameter(s): plan. Supply every declared parameter.`**

Pass `--param plan=<value>`. Every declared parameter is required, with no defaults.

**`Query does not declare parameter(s): bogus. Declared: plan.`**

The parameter name is not in the statement. Unknown names are refused rather than
ignored, because the driver would otherwise bind NULL and return plausible wrong rows.

**`Cannot sort by "revenue" — the query returns: id, name, total.`**

Sort names must match the query's *output* columns, not the table's. Alias the
expression in SQL and sort on the alias. The check exists because SQLite would accept
the name as a string literal and silently return the rows unordered.

**Rows repeat or go missing between pages**

`--offset` without `--sort`. SQL has no inherent order, so each page is free to come
back differently. Always sort when paging.

**Results look short**

The default cap is 100 rows. `--limit` raises it; `--json` reports `truncated`. For
totals, aggregate in SQL rather than counting returned rows.

## Recovery

`inspect` lists snapshots. `restore <workspace> <seq>` rewinds to one. `export` writes
the whole workspace as a tarball — worth doing before anything irreversible.
