INSERT INTO users (id, name, plan, created_at) VALUES
  (1, 'Ada',  'pro',  '2026-01-04'),
  (2, 'Linus','free', '2026-01-09'),
  (3, 'Grace','pro',  '2026-02-01');

INSERT INTO orders (id, user_id, status, amount, placed_at) VALUES
  (1, 1, 'fulfilled', 4200, '2026-02-10'),
  (2, 1, 'pending',   1500, '2026-02-12'),
  (3, 2, 'fulfilled',  900, '2026-02-14'),
  (4, 3, 'fulfilled', 7300, '2026-02-15');
