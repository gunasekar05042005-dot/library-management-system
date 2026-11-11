# AI output review

For each AI-generated output: what it generated, what was correct, what was incorrect, what was changed, and why. Evidence for the problems comes from experiments run against the code (not opinion); the regression tests named below prove each fix.

## 1. Plan and database design (prompts 1-2)
**Generated:** a three-table schema (`users`, `books`, `borrowings`), a rule-to-enforcement table, folder layout and build order.
**Correct:** `borrowings` as a junction table; `returned_at IS NULL` meaning "active" (no stored status that can drift); a partial unique index so a member cannot hold the same book twice; CHECK constraints so copies never go negative or above the total; `ON DELETE RESTRICT` to protect history.
**Incorrect or missing:** no `description` column and no provision for password reset or a profile, because the plan was made from a shortened brief; ISBN left optional although the brief lists it as book information; "total books" and "low availability" were not flagged as ambiguous.
**Changed:** `description` added with a safe upgrade step (`migrate()` in `db.py`); ISBN required in the admin form; the ambiguities documented in `ASSUMPTIONS_AND_AMBIGUITIES.md`.
**Why:** the schema must carry every field the brief lists, and an old database file must keep working.

## 2. Book catalogue (prompt 3)
**Generated:** list, search, genre filter, details page, default cover, seed data.
**Correct:** parameterised SQL (user input is never put into the SQL text); `sqlite3.Row` and `PRAGMA foreign_keys = ON` on every connection; the cover and availability markup shared through macros.
**Incorrect (confirmed):** `%` and `_` in the search box acted as wildcards (searching `%` returned every book); the page loaded every book at once; the cover fallback used an inline `onerror` attribute, which prevents a strict Content-Security-Policy.
**Changed:** wildcards escaped with an `ESCAPE` clause; 12 books per page with a pager; the fallback moved into `main.js`; CSP added.
**Why:** searches should match what the user typed, pages should stay fast with a large catalogue, and a strict CSP is a cheap defence against script injection.
**Tests:** `test_percent_and_underscore_are_searched_literally`, `test_catalog_is_paginated_and_clamps_bad_page_numbers`, `test_details_page_shows_description_and_default_cover`.

## 3. Registration and login (prompt 4)
**Generated:** registration, login, logout, role decorators, CSRF tokens, `create-admin` command.
**Correct:** salted password hashes; one generic login error; `session.clear()` before login; role re-read from the database each request; admin only via CLI; open-redirect guard; logout as POST.
**Incorrect (each reproduced):**
1. `SECRET_KEY` fell back to a hard-coded public default; a cookie signed with it opened `/admin/` (HTTP 200). *Critical.*
2. Login timing leaked which emails exist (91.7 ms for a registered email vs 0.8 ms for an unknown one) despite the generic message.
3. No length limits: a 100,000-character name and a 5,000-character email were accepted.
4. After a POST by a logged-out user the redirect remembered `?next=/borrow/1`, which led to a 405 page after login.
5. Every request, including CSS files, queried the user table.
6. No security headers (clickjacking possible); session cookie lacked the `Secure` option.
**Changed:** random key generated once and stored in `instance/secret.key` (or `SECRET_KEY`); a dummy hash is always checked; limits on name (100), email (254), search text and request size (64 KB); `next` kept only for GET; static files skipped; headers (`X-Frame-Options`, CSP, `nosniff`, `Referrer-Policy`) added; `Secure` cookie option via `SESSION_COOKIE_SECURE`; sessions now carry a fingerprint of the password hash, so they end when the password changes and cookies forged without it are rejected.
**Why:** a public signing key is equivalent to no authentication; timing and enumeration leaks undermine the generic error message; unbounded input is a cheap denial-of-service.
**Tests:** `tests/test_security_fixes.py` (one per item above).

## 4. Borrowing (prompt 5)
**Generated:** `borrow_book` in one transaction started with `BEGIN IMMEDIATE`, conditional `UPDATE ... WHERE available_copies > 0`, and a threaded test of the last-copy race.
**Correct:** taking the write lock before reading closes the check-then-write gap; the conditional update is a second guard; the unique index is a third.
**Incorrect (confirmed):**
- Every `IntegrityError` was reported as "already borrowed"; a foreign-key failure (unknown user) was disguised as that message.
- "Today" came from the server's timezone, so "overdue" could flip at the wrong hour for the library.
- The race tests passed even when the lock was removed, because the code ran too quickly for threads to overlap (a weak test).
**Changed:** only a `UNIQUE` failure maps to the friendly message, anything else surfaces; dates use a configured timezone (`services/clock.py`, default Asia/Kolkata); the race tests pause between check and write so removing the lock now makes them fail.
**Why:** misleading errors hide real faults, and a test that cannot fail gives false confidence.

## 5. Returning (prompt 6)
**Generated:** `return_book` with an ownership filter and a conditional `UPDATE ... AND returned_at IS NULL` before the copy is given back.
**Correct:** closing the loan first means a double submit changes nothing; another member's loan gets the same "not found" answer as a made-up ID; threaded double-return test.
**Incorrect (confirmed):** the return date was "today", but the table requires `returned_at >= borrowed_at`; if the clock or timezone moved backwards the return failed with an error and the loan could never be closed (and still counted toward the member's limit).
**Changed:** the return date is `max(today, borrowed_at)`.
**Why:** a rare clock change must not make a member's loan permanent.
**Test:** `test_return_never_writes_a_date_before_the_borrow_date`.

## 6. Dashboards (prompt 7)
**Generated:** member dashboard (replacing a separate "My books" page) and admin dashboard with five live figures.
**Correct:** every number is a query; one "today" value feeds all overdue checks so pages agree.
**Questionable (decision, not a bug):** "low availability" lists any title with 2 or fewer available copies, including a two-copy title that is fully on the shelf; "total books" counts titles.
**Changed:** nothing in behaviour; both definitions documented as assumptions.
**Why:** the brief does not define them; the choice is stated so a reviewer can disagree knowingly.

## 7. First test suite (prompt 8)
**Generated:** 59 tests including races, refresh and simulated multiple tabs; `TEST_CASES.md`.
**Correct:** broad coverage of the rules; concurrency tests with real threads and separate connections.
**Incorrect:** all 59 passed while nine real problems existed (section 3-5), and the lock-removal check initially went undetected.
**Changed:** regression tests for every confirmed problem, tests for each feature added later (141 tests now), and checks that deliberately remove safeguards to prove the tests fail.
**Why:** a passing suite only proves the behaviour it asks about.

## 8. The code review itself (prompt 9)
**Generated:** nine confirmed problems with evidence, risks needing tests, and things checked and found sound.
**Correct:** each confirmed item was reproduced by running code.
**Incorrect:** an earlier note listed the default `SECRET_KEY` as a deployment reminder; it was the most serious issue and was under-rated.
**Changed:** severity corrected to critical and fixed first.

## 9. Gap analysis and completion (prompts 10-11)
**Generated:** a comparison of the full brief with what existed, then the missing features: profile, password reset, book description, borrowing history, admin add/edit books with the total-copies rule, member and borrowing lists, and these documents.
**Verified:** 141 automated tests pass; the real server was started, an admin created through the command, and a login, search and admin page visited. Concurrency tests were repeated 3 times without failure.
**Not verified:** real-browser multi-tab behaviour, real email delivery, behaviour under heavy load.
