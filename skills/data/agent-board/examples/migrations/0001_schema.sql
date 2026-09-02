CREATE TABLE users (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  plan       TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE orders (
  id       INTEGER PRIMARY KEY,
  user_id  INTEGER NOT NULL REFERENCES users(id),
  status   TEXT NOT NULL,
  amount   INTEGER NOT NULL,
  placed_at TEXT NOT NULL
);

CREATE INDEX idx_orders_user ON orders(user_id);
