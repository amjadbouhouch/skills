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
`{ type: "saved_query", query: <saved query name>, parameters?, limit?, offset?, sort? }`
and `query` must name a saved query that exists. See "How many rows, in what order"
below for the last three.

| Type | Reads data | Required | Optional |
|---|---|---|---|
| `metric_card` | yes | `value` | `title`, `format` |
| `data_table` | yes | — | `title`, `columns`, `filter` |
| `bar_chart` | yes | `mapping` | `title`, `format` |
| `line_chart` | yes | `mapping` | `title`, `format` |
| `filter` | no | `field`, `control` | `label`, `optionsQuery` |

Plus `id` and `type` on every component, and `source` on every type that reads data.

- `value` on a metric card names a column in the query result.
- `mapping` is `{ x, y }` and both must name columns. A chart without a usable mapping
  has nothing to plot, which is why it is required rather than defaulted.
- `columns` on a data table selects and orders which result columns to show.
- `control` on a filter is one of `select`, `text`, `number`, `date`, `daterange`.
  `optionsQuery` names a saved query supplying the choices for a `select`.
- `filter` on a data table is `{ field, operator, value }`, with `operator` one of
  `eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `contains`.

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

The same three are accepted in the query request body, so a renderer can page and
re-sort without republishing. `truncated` in the response means "a further row exists" —
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
