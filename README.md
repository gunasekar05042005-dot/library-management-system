# Library Management System

A small web application where members browse books, borrow and return them and track their borrowing history, and administrators manage the catalogue and see how the library is doing.

**Stack:** Python 3.10+, Flask, SQLite, HTML/CSS/JavaScript (no front-end framework).

## Features

| Area | What it does |
|---|---|
| Accounts | Register, log in/out, view and update profile, reset a forgotten password |
| Catalogue | Browse, search by title or author, filter by genre or availability, book details with description, default cover image |
| Borrowing | Borrow (max 3 at a time, 14-day loan), return, current loans with due dates, full history with Borrowed / Returned / Overdue status |
| Member dashboard | Books borrowed, overdue count, next due date, current loans with Return buttons |
| Admin | Dashboard (members, books, active and overdue borrowings, low availability), add/edit books, member list, all borrowing records, read-only **Database** viewer (users, books and borrowings; password hashes are never shown) |

## Quick start

```bash
python -m venv venv
source venv/bin/activate            # Windows PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt

python seed.py                      # creates instance/library.db and 13 sample books
flask --app app create-admin        # prompts for name, email and password
flask --app app run --debug         # open http://127.0.0.1:5000
```

Register a member from the **Register** page. Administrators sign in on their own page, **http://127.0.0.1:5000/admin/login** (also reachable from the **Admin login** link), with the account created by `create-admin`, and land on the admin dashboard.

**Password reset:** there is no email server. The reset link is written to the terminal running the server. With `--debug` (or `SHOW_RESET_LINK=1`) the link is also shown on the page so it can be demonstrated without reading the log.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| The terminal stops showing new lines, or pages hang until you press a key | In Windows Command Prompt, **clicking or selecting text in the window pauses the running program** (QuickEdit mode, the title shows "Select"). Press **Enter** or **Esc** to resume. Avoid clicking in the server window; to switch it off, right-click the title bar, Properties, untick QuickEdit Mode. Windows Terminal avoids most of this. |
| "Database unavailable" page | Another program has the database file open (a database viewer, or a second copy of the server). Close it and retry. If it says the database is not set up, stop the server and run `python seed.py`. |
| "Request not accepted ... another tab" | You signed in or out in another tab. Reload the page and try again. |
| Cannot sign in as two users in one browser | All tabs of one browser share one session cookie, so only one user can be signed in per browser. Use a private window, a second browser or profile, or open one user at `http://localhost:5000` and the other at `http://127.0.0.1:5000`. |
| Old data after upgrading | The database file is now `instance/library.db`. To keep an older `instance/library.sqlite`, stop the server and rename it (and any matching `-wal` and `-shm` files) to `library.db`; or run `python seed.py` to start fresh. |

You can open `instance/library.db` in a tool such as DB Browser for SQLite. Close the tool before using the app, because an open writer can lock the file.

## Configuration (environment variables, all optional)

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs session cookies and reset links | A random key is generated once and saved in `instance/secret.key` |
| `LIBRARY_TIMEZONE` | Timezone used for due dates and "overdue" | `Asia/Kolkata` |
| `SHOW_RESET_LINK` | `1` shows the reset link on the page (demo only) | Off, except in `--debug` |
| `SESSION_COOKIE_SECURE` | `1` when served over HTTPS | Off |

Do not run with `--debug` in production.

## Tests

```bash
python -m pytest        # 160 tests, about 40 seconds
```

The suite covers registration and login, access control, the catalogue, borrowing, returning, history, profile, password reset, admin book management, dashboards, concurrency (simultaneous borrows, double returns, edits racing borrows), browser refresh, stale tabs, database constraints, and a regression test for every problem found in the code review. `docs/TEST_CASES.md` lists each case with its expected result.

## Project structure

```
app/
  __init__.py        app factory, security headers, error pages
  auth.py            register, login, logout, password reset, role decorators, create-admin command
  account.py         profile
  books.py           catalogue and book details
  member.py          borrow, return, member dashboard, history
  admin.py           admin dashboard, add/edit books, member and borrowing lists
  security.py        CSRF protection
  db.py              connections, schema creation and upgrade
  schema.sql         tables, constraints, indexes
  services/
    borrowing.py     ALL borrow/return rules and transactions
    catalog.py       book validation and the total-copies rule
    reports.py       history and admin listings
    stats.py         admin dashboard figures
    clock.py         "today" in the library's timezone
    pagination.py
  templates/ static/
tests/               160 automated tests
docs/                analysis, rules, assumptions, AI prompts and review, test cases, known issues
seed.py              sample data
```

## Design decisions in brief

- **Business rules live in `services/borrowing.py`**, so routes stay thin and the rules are easy to test.
- **The database is the last line of defence:** CHECK constraints (copies never negative, available never above total), foreign keys, a unique ISBN, and a partial unique index that forbids a second active loan of the same book by one member.
- **Borrow and return are single transactions** started with `BEGIN IMMEDIATE`, each step conditional (`... WHERE available_copies > 0`, `... WHERE returned_at IS NULL`) and checked by affected row count. Two requests for the last copy are therefore processed one after the other.
- **Overdue is derived** (`due_date < today`), never stored, so it cannot go stale.
- **Security:** hashed passwords, generic login errors, constant-time-ish login, CSRF tokens on every POST, sessions that end when the password changes, role re-read from the database on each request, open-redirect guard, CSP and other security headers, input length limits.

## Documents

| File | Content |
|---|---|
| `docs/REQUIREMENT_ANALYSIS.md` | Requirements, scope, traceability to code and tests |
| `docs/BUSINESS_RULES_AND_VALIDATIONS.md` | BR-01 to BR-06, validations, calculations, edge cases |
| `docs/ASSUMPTIONS_AND_AMBIGUITIES.md` | Answers to the three ambiguous requirements and other assumptions |
| `docs/AI_PROMPTS_USED.md` | The prompts used to build the project |
| `docs/AI_OUTPUT_REVIEW.md` | What the AI produced, what was right and wrong, what was changed and why |
| `docs/TEST_CASES.md` | Functional, negative and edge-case test cases with expected results |
| `docs/KNOWN_ISSUES.md` | Known issues and limitations |
