# Requirement analysis

## 1. Purpose and scope
A basic library web application. Members browse books, borrow and return them and track their history. Administrators manage books and monitor the library. Out of scope (optional bonus items, not built): overdue fines, reservations or waitlists, ratings and reviews, recently viewed books, AI recommendations.

## 2. Actors
| Actor | Can | Cannot |
|---|---|---|
| Visitor (not logged in) | Register, log in, request a password reset | See any catalogue or account page |
| Member | Browse and search, borrow, return, view own dashboard and history, update own profile | See other members' data, add or edit books, open admin pages |
| Administrator | Everything an admin page offers: dashboard, add/edit books, members, all borrowings, own profile | Borrow or return books (see assumptions) |

## 3. Functional requirements and traceability

| ID | Requirement | Where implemented | Tests |
|---|---|---|---|
| FR-U1 | Register (unique email, 8+ char password, mandatory fields, valid email) | `auth.register`, `validate_registration` | `test_auth`, `test_validation`, `test_edge_cases` |
| FR-U2 | Log in / out with safe session handling | `auth.login`, `auth.logout` | `test_auth`, `test_security_fixes` |
| FR-U3 | View and update profile | `account.profile` | `test_history_and_profile` |
| FR-U4 | Password reset | `auth.forgot_password`, `auth.reset_password` | `test_password_reset` |
| FR-B1 | View catalogue | `books.catalog` | `test_catalog` |
| FR-B2 | Search by title or author | `books.catalog` | `test_catalog` |
| FR-B3 | Filter by genre (and by availability) | `books.catalog` | `test_catalog` |
| FR-B4 | Book details (title, author, cover, genre, ISBN, total and available copies, description) | `books.detail`, `schema.sql` | `test_catalog` |
| FR-B5 | Default cover when none | `_macros.html`, `main.js` | `test_catalog` |
| FR-B6 | Admin adds and edits books | `admin.new_book`, `admin.edit_book`, `services/catalog.py` | `test_admin` |
| FR-L1 | Borrow a book | `services/borrowing.borrow_book`, `member.borrow` | `test_borrowing`, `test_edge_cases` |
| FR-L2 | Return a book | `services/borrowing.return_book`, `member.return_loan` | `test_returning` |
| FR-L3 | View currently borrowed books | `member.dashboard` | `test_dashboards` |
| FR-L4 | Borrowing history with statuses Borrowed / Returned / Overdue | `member.history`, `services/reports.py` | `test_history_and_profile` |
| FR-D1 | Member dashboard: current books, due dates, overdue | `member.dashboard` | `test_dashboards` |
| FR-D2 | Admin dashboard: members, books, active, overdue, low availability | `admin.dashboard`, `services/stats.py` | `test_dashboards` |
| FR-A1 | Admin lists all members and all borrowing records | `admin.members`, `admin.borrowings` | `test_admin` |
| FR-A2 | Clear administrator sign-in page | `auth.admin_login`, `admin_login.html` | `test_admin_access` |
| FR-A3 | Administrators can see all database information (read-only) | `admin.database`, `admin.database_table` | `test_admin_access` |

## 4. Non-functional requirements
| Area | Requirement | How it is met |
|---|---|---|
| Data integrity | Copy counts and loans always agree | One transaction per borrow/return/edit, CHECK constraints, foreign keys |
| Concurrency | No double-borrow of the last copy | `BEGIN IMMEDIATE` plus conditional updates; threaded tests |
| Security | Protect accounts and enforce roles | See README "Design decisions"; regression tests in `test_security_fixes` |
| Usability | Clean, responsive, simple | Mobile-first CSS, one layout language, flash messages, keyboard focus styles |
| Maintainability | Rules in one place, tested | `services/` layer, 160 automated tests |

## 5. Data requirements
Three tables: `users` (role member/admin), `books` (including `description`, `cover_url`, `total_copies`, `available_copies`), `borrowings` (one row per loan; `returned_at` NULL means still borrowed). Status Borrowed / Returned / Overdue is derived. Full schema: `app/schema.sql`.

## 6. Constraints and dependencies
Flask, SQLite (single writer; WAL mode), Python 3.10+, `tzdata` for timezones. No email service, so password reset links are logged (see known issues).
