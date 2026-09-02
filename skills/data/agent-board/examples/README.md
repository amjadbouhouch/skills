# Worked example

An orders dashboard over a two-table schema. Every file here was run through the CLI
end to end — migrated, validated, published, and queried — so it is a working starting
point rather than an illustration.

| File | What it shows |
|---|---|
| `migrations/0001_schema.sql` | DDL: `users`, `orders`, one index |
| `migrations/0002_seed.sql` | Rows, in a migration — the only write path |
| `app.json` | All five component types, one parameterized saved query |

Reproduce it:

```sh
agent-board init
agent-board workspace create analytics
cp migrations/*.sql workspaces/analytics/migrations/
agent-board migrate analytics
agent-board inspect analytics
agent-board publish analytics app.json --reason "initial dashboard" --expect-version 0
agent-board query analytics --saved revenue_by_user
agent-board query analytics --saved orders_by_plan --param plan=pro
```

Points worth copying:

- `revenue_by_user` aggregates in SQL and returns exactly the two columns the chart's
  `mapping` names. Shape the result for the component rather than filtering client-side.
- `orders_by_plan` declares `plan` and references it as `:plan`. The `data_table` binds
  it through `source.parameters`, and the `plan-filter` component drives it at run time.
- `plans` exists only to populate the filter's `optionsQuery` — a saved query is the
  supported way to supply choices.
- The seed migration is separate from the schema migration. Keeping them apart means a
  later schema change does not force you to re-read the data you inserted.
