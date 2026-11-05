PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  full_name     TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
  email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  phone         TEXT,
  role          TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin')),
  created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS books (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  title            TEXT NOT NULL CHECK (length(trim(title)) > 0),
  author           TEXT NOT NULL CHECK (length(trim(author)) > 0),
  isbn             TEXT UNIQUE,
  category         TEXT NOT NULL,
  cover_url        TEXT,                       -- NULL = use the default cover
  description      TEXT,
  total_copies     INTEGER NOT NULL CHECK (total_copies >= 0),
  available_copies INTEGER NOT NULL CHECK (available_copies >= 0),
  created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (available_copies <= total_copies)
);

CREATE TABLE IF NOT EXISTS borrowings (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE RESTRICT,
  borrowed_at TEXT NOT NULL,
  due_date    TEXT NOT NULL,
  returned_at TEXT,
  CHECK (due_date >= borrowed_at),
  CHECK (returned_at IS NULL OR returned_at >= borrowed_at)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_active_loan
  ON borrowings (user_id, book_id) WHERE returned_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_borrowings_user ON borrowings (user_id);
CREATE INDEX IF NOT EXISTS idx_borrowings_book ON borrowings (book_id);
CREATE INDEX IF NOT EXISTS idx_books_category  ON books (category);
