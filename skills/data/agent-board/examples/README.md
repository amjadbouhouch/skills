# Worked example

An orders dashboard over a two-table schema. Every file here was run through the CLI
end to end — migrated, loaded, validated, published, and queried — so it is a working
starting point rather than an illustration.

| File | What it shows |
|---|---|
| `migrations/0001_schema.sql` | DDL only: `users`, `orders`, one index |
| `data/users.json`, `data/orders.json` | Rows, loaded through `rows insert` |
| `app.json` | All five component types, one parameterized saved query |

Reproduce it:

```sh
agent-board init
agent-board workspace create analytics
cp migrations/*.sql workspaces/analytics/migrations/
agent-board migrate analytics
agent-board rows insert analytics users  --data-file data/users.json
agent-board rows insert analytics orders --data-file data/orders.json
agent-board inspect analytics
agent-board publish analytics app.json --reason "initial dashboard" --expect-version 0
agent-board query analytics --saved revenue_by_user
agent-board query analytics --saved orders_by_plan --param plan=pro
agent-board start --port 4000
```

Points worth copying:

- The migration carries schema and nothing else. Data arrives through `rows`, so a
  later correction is an ordinary update rather than another permanent ledger entry.
- Load order follows the foreign key: `users` before `orders`.
- `revenue_by_user` aggregates in SQL and returns exactly the two columns the chart's
  `mapping` names. Shape the result for the component rather than filtering client-side.
- `orders_by_plan` declares `plan` and references it as `:plan`. The `data_table` binds
  it through `source.parameters` for the first render, and `plan-filter` rebinds it at
  run time through `targets: [{ component: "orders-table", parameter: "plan" }]`.
- `targets` is required on every filter. Without it the specification does not validate,
  because a control that changes nothing is the failure the DSL exists to catch.
- `plans` exists only to populate the filter's `optionsQuery` — a saved query is the
  supported way to supply choices.
- Re-running the two `rows insert` lines fails on the primary key, which is correct.
  `rows upsert analytics users --data-file data/users.json --on-conflict id` is the
  version that is safe to run twice.
