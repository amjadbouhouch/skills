# The application DSL

Version `1.0`. Validated by `agent-board validate <file>`, and again as the first gate of
`agent-board publish`.

Throughout: **unknown properties are errors**, at every level — top level, page, saved
query, component, source, mapping, filter, navigation entry. The validator reports the
offending key and lists what is allowed, so read the error rather than guessing.

Ids (`id` on the application, pages and components) are lowercase kebab-case: they must
match `^[a-z0-9][a-z0-9-]*$`.

## Top level

| Field | Required | Notes |
|---|---|---|
| `dslVersion` | yes | `"1.0"` |
| `id` | yes | kebab-case |
| `title` | yes | non-empty |
| `pages` | yes | array, see below |
| `savedQueries` | no | array; omit only for a page with no data components |
| `navigation` | no | array of `{ label, page, icon? }`; `page` must be a real page id |
| `actions` | no | reserved |
| `theme` | no | reserved |

## Saved queries

`{ name, sql, description?, parameters? }`

- `name` must be unique. Duplicates are rejected, because every reference to that name
  would be ambiguous.
- `sql` must be non-empty and read-only — start it with `SELECT` or `WITH`.
- Reference a parameter as `:name` in the SQL and declare it in `parameters`. Every
  declared parameter must be supplied at call time; supplying an undeclared one is an
  error.

## Pages

`{ id, type, title, components }`

`type` is `"dashboard"` — the only page type in 1.0. Component ids must be unique within
a page.

## Components

Each type declares what it requires and everything it may carry. `source` is
`{ type: "saved_query", query: <saved query name>, parameters?, limit?, offset?, sort?, filter? }`
and `query` must name a saved query that exists. See "How many rows, in what order"
below for `limit`, `offset` and `sort`.

`source.filter` is a non-empty array of `{ field, operator, value }` conditions joined
with AND, applied to the columns the query returns. Use it to shape one saved query for
several components instead of writing near-duplicate SQL for each.

| Type | Reads data | Required | Optional |
|---|---|---|---|
| `metric_card` | yes | `value` | `title`, `format` |
| `data_table` | yes | — | `title`, `columns`, `filter` |
| `bar_chart` | yes | `mapping` | `title`, `format` |
| `line_chart` | yes | `mapping` | `title`, `format` |
| `filter` | no | `field`, `control`, `targets` | `label`, `optionsQuery`, `operator` |

Plus `id` and `type` on every component, and `source` on every type that reads data.

- `value` on a metric card names a column in the query result.
- `mapping` is `{ x, y }` and both must name columns. A chart without a usable mapping
  has nothing to plot, which is why it is required rather than defaulted.
- `columns` on a data table selects and orders which result columns to show.
- `control` on a filter is one of `select`, `text`, `number`, `date`, `daterange`.
  `optionsQuery` names a saved query supplying the choices for a `select`.
- `targets` on a filter is required — see "A filter control has to drive something".
- `filter` on a data table is a single fixed condition `{ field, operator, value }`,
  baked into the specification. It is not the same key as `source.filter`, which is an
  *array* of conditions; a component may carry both.

Filter operators, everywhere they appear: `eq`, `neq`, `lt`, `lte`, `gt`, `gte`,
`contains`. The same seven exist as symbols on the command line — `= != < <= > >= ~` —
so a condition means the same thing in either spelling. `contains` compiles to `instr()`
rather than `LIKE`, so a literal `%` in the value stays a `%`.

## A filter control has to drive something

`targets` is required, and it must be a non-empty array. A control the user can change
to no effect is the failure this DSL exists to reject, so the validator refuses the
specification rather than rendering a dead dropdown.

Each entry is `{ component, parameter? }`:

- `component` must name another component **on the same page** that reads data. A filter
  cannot target itself, and cannot target a component with no `source`.
- With no `parameter`, the target's result is *narrowed*: the filter's own `field` and
  `operator` are applied to the rows the query returned.
- With `parameter`, the value *binds* one of the target query's declared parameters. The
  name is checked against the SQL at validation time, so renaming `:plan` surfaces as an
  error rather than as an empty table at run time.

```json
{ "id": "plan-filter", "type": "filter", "field": "plan", "control": "select",
  "operator": "eq", "optionsQuery": "plans",
  "targets": [{ "component": "orders-table", "parameter": "plan" },
              { "component": "revenue-chart" }] }
```

Targets resolve after the whole page is read, so a filter may name a component declared
below it.

## How many rows, in what order

A component states its own data needs; a renderer should not have to guess them.

```json
"source": {
  "type": "saved_query", "query": "products_list",
  "limit": 500, "sort": ["-revenue", "name"]
}
```

- `limit` — integer 1..10000. **Omitting it caps the component at 100 rows**, and a
  table over that renders its first page while saying nothing about the rest. Set it
  whenever the query can return more.
- `sort` — array of result columns, `-name` for descending. The names must be columns
  the query returns, not table columns; alias in SQL and sort on the alias.
- `offset` — rows to skip. **Only meaningful with `sort`.** SQL has no inherent row
  order, so paging an unordered query repeats rows on one page and skips them on the
  next, and nothing reports it.

`limit`, `offset`, `sort` and `filter` are all accepted in the query request body too,
so a renderer can page, re-sort and narrow without republishing. `truncated` in the response means "a further row exists" —
it is what a next-page control should be driven from, and it is exact: a page ending on
the last row reports `false`.

## Minimal valid application

```json
{
  "dslVersion": "1.0",
  "id": "analytics",
  "title": "Analytics",
  "savedQueries": [
    { "name": "revenue", "sql": "SELECT SUM(amount) AS revenue FROM orders" }
  ],
  "pages": [
    {
      "id": "overview",
      "type": "dashboard",
      "title": "Overview",
      "components": [
        { "id": "revenue", "type": "metric_card", "title": "Revenue",
          "source": { "type": "saved_query", "query": "revenue" },
          "value": "revenue" }
      ]
    }
  ]
}
```

`examples/app.json` is the fuller version, exercising all five component types against
the schema in `examples/migrations/`.
