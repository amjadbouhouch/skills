# The HTTP surface

`agent-board start` returns three routes and nothing else. There is no route that takes
SQL: a caller names a saved query from the published specification and supplies
parameters. A query you forgot to publish does not exist as far as the server is
concerned.

Use this when you are writing a page to serve with `start --static <dir>`. Serving the
page from the same origin is why none of this needs CORS.

## Routes

| Method | Path | Returns |
|---|---|---|
| `GET` | `/workspaces/<id>/application` | The current published specification |
| `GET` | `/workspaces/<id>/application/versions` | `{ current, versions: [...] }` |
| `POST` | `/workspaces/<id>/queries/<name>` | Rows for one saved query |

`<id>` matches `^[a-z0-9][a-z0-9-]{0,63}$`. A page fetches `application` to learn what to
draw — pages, components, each component's `source` — then posts once per component.

## Running a query

```js
const res = await fetch(`/workspaces/analytics/queries/orders_by_plan`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({
    parameters: { plan: "pro" },
    limit: 500,
    offset: 0,
    sort: ["-amount"],
    filter: [{ field: "status", operator: "eq", value: "fulfilled" }],
  }),
});
const { columns, rows, rowCount, truncated, limit } = await res.json();
```

Every field of the body is optional except the parameters the query declares. Bodies are
capped at 64 KB, which is far more than parameters need and far less than a payload
worth scanning.

- `parameters` — every declared parameter is required; an undeclared name is refused.
  A value may be a string, number, boolean or `null`; numbers and booleans are coerced
  to strings and `null` binds SQL NULL. Anything else (an object, an array) is a 400.
- `limit` — integer 1..10000. Default 100.
- `offset` — only meaningful alongside `sort`; an unordered query pages differently each
  time and nothing reports it.
- `sort` — array of **result** column names, `-name` for descending. Checked against the
  columns the query actually returns.
- `filter` — array of `{ field, operator, value }` joined with AND, `operator` one of
  `eq neq lt lte gt gte contains`.

`limit`, `offset`, `sort` and `filter` are the same four a component declares in its
`source`, so a renderer can page and re-sort without republishing. Send the component's
declared values as the first page, then vary them.

`truncated` is the "there is a next page" flag and it is exact — a page ending on the
last row reports `false` rather than inferring from a full page. Drive a next-page
control from it rather than comparing `rowCount` to `limit`.

## Errors

Failures come back as `{ "error": "<code>", "message": "…" }` with a real status. The
codes are stable, so branch on `error` rather than matching message text.

| Status | Code | Cause |
|---|---|---|
| 400 | `invalid_workspace_id` | The id does not match the pattern |
| 400 | `invalid_parameters` | Not an object, or a name the query does not declare |
| 400 | `invalid_limit` / `invalid_offset` | Out of range, or not a whole number |
| 400 | `invalid_sort` | Not an array, or a column the query does not return |
| 400 | `invalid_filter` | Malformed condition, or an unknown operator |
| 403 | `forbidden` | An `authorize` hook denied it (not configured by `start`) |
| 404 | `query_not_found` | The name is not in the published specification |
| 404 | `not_found` | No route, and no such file under `--static` |
| 413 | `body_too_large` | Over 64 KB |
| 500 | `query_failed` | The SQL itself failed at run time |
| 504 | `query_timeout` | The query passed the execution deadline and was cancelled |

Each query runs in a child process that is killed on deadline, which is why a runaway
query returns 504 rather than hanging the server. Anything not in this table is an
opaque 500 by design — internal errors are not narrated to a browser.

## What the server does not do

There is no write route. `rows insert|upsert|update|delete` is the CLI, and it stays
there: the preview receipt, the row cap and the audit before-image are gates a browser
caller has no way to satisfy. If a user needs to edit data, do it through the CLI on
their behalf.
