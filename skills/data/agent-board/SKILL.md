---
name: agent-board
description: Use it to build and run a persistent data application — dashboard, metrics view, internal reporting tool — on the AgentBoard runtime, writing SQL migrations for schema and a declarative JSON specification for the UI instead of application code, then loading and editing the data through its `rows` commands. Reach for it whenever the user wants a dashboard, admin panel, internal tool, or "somewhere to see this data" backed by SQLite; whenever they want to load a spreadsheet's worth of records into one, correct rows already in it, or add a table to one; and whenever an `agent-board.json` or a `workspaces/` directory is present. Do not use it for querying a database the user already runs, or for a UI that needs custom components.
---

# AgentBoard

AgentBoard runs data applications you describe rather than code you write. You author
two artifacts — SQL migrations and a JSON specification — and the runtime owns storage,
versioning, query safety and serving. The application keeps working after you exit,
which is the point: nothing you build here depends on your process staying alive.

Work through the CLI. `agent-board help` is the authority on flags; this skill covers
the model, the order of operations, and the refusals you will hit.

## Getting the runtime

Check before installing — `agent-board --version` prints a version if it is already
there. If not:

```sh
curl -fsSL https://raw.githubusercontent.com/amjadbouhouch/agent-board/main/install.sh | sh
```

A single binary lands in `$HOME/.agent-board/bin`, verified against a published sha256.
There is nothing to build and no runtime to install alongside it.

With no terminal attached — which is the usual case when you are running commands on
someone's behalf — the installer will not edit their shell profile. It prints the export
line instead, so put the directory on the path for your session and carry on:

```sh
export PATH="$HOME/.agent-board/bin:$PATH"
```

Pass `--modify-path` to persist it in their profile, `--dir <path>` to install elsewhere,
or `--version vX.Y.Z` to pin. Flags go after `-s --` when piping:
`… | sh -s -- --modify-path`.

## The boundary

You own the business schema and the specification. The runtime owns what keeps them
safe. Two consequences shape everything below:

- **Migrations own schema; `rows` owns data.** A migration carries DDL, and the backfill
  that belongs with a schema change — add a column, populate it, constrain it. The
  initial load, corrections and ongoing edits go through `rows`, so the ledger does not
  become a replay log of every change anyone ever made.
- **You never write SQL that changes data.** `rows` takes a table, columns and filters
  and composes the statement itself. There is no way to hand it an UPDATE.
- **Published SQL is the only SQL a user can run.** Callers pass a saved-query name and
  parameters, never statement text. So a query you forget to publish does not exist.

## The loop

```sh
agent-board init                                   # once per project
agent-board workspace create <name>                # one workspace per application
# write workspaces/<name>/migrations/0001_schema.sql
agent-board migrate <name>                         # snapshots, applies, integrity-checks
agent-board rows insert <name> <table> --data-file rows.json   # load the data
agent-board inspect <name>                         # confirm tables and row counts
# write the specification
agent-board validate app.json                      # cheap, no workspace needed
agent-board publish <name> app.json --reason "…"   # runs the gates
agent-board query <name> --saved <query>           # verify what users will see
agent-board start --port 4000                      # serve it
```

Run `inspect` after migrating and `query --saved` after publishing. Both are fast, and
they are how you find out that what you built matches what you intended — the
specification and the database can disagree in ways only execution reveals.

## Migrations

Files are `migrations/NNNN_name.sql`, applied in numeric order, each in its own
transaction, recorded in a ledger with a checksum. `migrate` snapshots first and
restores that snapshot if anything fails, so a broken migration leaves no wreckage.

Number new migrations **above every existing one**. `migrate` applies only versions
greater than the highest already applied, so a file that fills an earlier gap is
skipped in silence — it reports "up to date" and your table never appears. If you are
unsure what has been applied, `inspect` lists it.

Once applied, a migration's contents are frozen: editing the file changes its checksum
and the next `migrate` refuses. Correct a mistake with a new migration.

Rejected inside migrations, because they reach past the schema the runtime can reason
about: `PRAGMA`, `ATTACH`, `DETACH`, `VACUUM`, `load_extension`. Also rejected is any
occurrence of the platform prefixes `_agentboard_`, `_auth_`, `_audit_` — the check is a
plain substring scan, so *a comment mentioning `_audit_` fails the migration*. Say
"audit" without the underscores.

## Writing rows

```sh
agent-board rows insert <ws> <table> --data-file rows.json [--returning]
agent-board rows update <ws> <table> --set <col>=<value> --where <col><op><value>
agent-board rows delete <ws> <table> --where <col><op><value>
```

**Never transcribe a data file by hand.** Reading a CSV and retyping 400 rows as JSON
costs a fortune in tokens and, far worse, quietly drops and mangles values with nothing
to catch it. Write a short script that converts the source into the JSON array, run it,
then load the file with `--data-file`. A program copying rows is exact; you are not.

`insert` applies directly — it can only add. `update` and `delete` **preview by
default**: they report how many rows match, write nothing, and print a receipt.

```
Preview: 2 rows in "products" would be updated.
Nothing was written. Re-run with --apply <receipt> to write it.
receipt: 689b0bef65348098
```

Pass that receipt back with `--apply` to write. It is refused if the matched rows or the
change itself moved since the preview, so a receipt cannot be redeemed against a
different edit. Re-run the preview and use the new one.

Both refuse without `--where`, and refuse past the row cap without `--force`. Filters are
`<column><operator><value>` with operators `!= <= >= = < > ~`, where `~` means contains.
Combine several `--where` flags for AND. Use `@null` for SQL NULL — a bare `null` is the
literal text.

`--returning` hands back the rows as stored, which is **the only way to learn a generated
key**: a UUID default leaves nothing to query back by.

A value is checked against the column's type before it is written. A number carrying a
thousands separator is the usual casualty — SQLite would store `"1,200"` as text in an
INTEGER column without complaint, and every later `SUM()` would be wrong. Convert in your
conversion script, not in the database.

Applied changes are recorded in `_audit_row_changes` with a before-image of what a delete
or update replaced. Previews record nothing.

### Columns mean what the schema says

`created_at` works as a column `DEFAULT`. **`updated_at` needs a trigger** — `rows update`
will not touch a column because of its name, so a column with only a `DEFAULT` records
insert time forever while looking correct:

```sql
CREATE TRIGGER items_touch AFTER UPDATE ON items
BEGIN
  UPDATE items SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = NEW.id;
END;
```

## The specification

One JSON object describing saved queries and the pages that display them. Validate it
with `agent-board validate` before publishing; validation needs no workspace, so it
costs nothing to run repeatedly while drafting.

Every component declares what its type requires, and **unknown properties are errors**.
That is deliberate and it is the failure this catches most often: a misspelled `filtr`
would otherwise render a table with no filter and no complaint. If validation reports an
unknown property, you have a typo, not a missing feature.

The full contract — every component type, its required and optional fields, the allowed
filter operators and controls — is in `references/dsl.md`. Read it before writing a
specification; the shapes are small but exact.

A working example using all five component types, with the migrations that back it, is
in `examples/`. Start from it rather than from memory.

### Parameters

Declare a parameter in the saved query and reference it as `:name` in the SQL:

```json
{ "name": "orders_by_plan",
  "sql": "SELECT id, status FROM orders WHERE plan = :plan",
  "parameters": [{ "name": "plan", "type": "string" }] }
```

Every declared parameter must be supplied at call time, and supplying an undeclared one
is an error. Both directions are enforced because the underlying driver binds NULL for a
name the statement never declared, which returns plausible wrong rows instead of
failing — a silent wrong answer is worse than a refusal.

## Publish refuses on purpose

Four gates run before anything is written, and a refusal is information:

1. **DSL validation** — the specification is malformed.
2. **`--expect-version <n>`** — the workspace moved since you read it. Pass the version
   you saw from `inspect`; the publish aborts rather than overwriting someone else's.
3. **Read-only check** — a saved query is not a `SELECT` or `WITH`.
4. **Smoke test** — every saved query is *executed* at `LIMIT 1` with parameters bound
   to NULL.

Gate 4 is the one that catches real bugs. Executing rather than compiling is deliberate:
`json_extract` over malformed JSON compiles clean and fails at run time, as does a
column name that no longer exists. When it fires, the specification and the database
disagree — fix one of them, and do not work around the gate.

History is append-only. `rollback <workspace> <version>` republishes an old version as a
*new* one through the same gates, so nothing is lost and nothing skips validation.

## Queries

`query` is read-only twice over: a keyword allowlist, then `PRAGMA query_only`. Ad-hoc
SQL is available for your own verification, but anything a user will run must be a saved
query in the published specification.

Use `--json` when you need to read the result programmatically rather than display it.
Results are capped (default 100 rows, `--limit` to raise); check `truncated` in the JSON
output before drawing conclusions about totals from returned rows — aggregate in SQL
instead of counting rows client-side.

## When something fails

`references/troubleshooting.md` maps the CLI's actual error messages to what causes them
and what to do. Consult it when a command refuses; the messages are specific, and
guessing at them wastes a cycle you can spend reading.
