# Known issues and limitations

## Limitations by design
| Item | Detail |
|---|---|
| Password reset email | No email server: the reset link is written to the server log (and shown on the page in demo mode). A real deployment needs SMTP or an email service. |
| No rate limiting | Login, registration and reset requests are not throttled; no account lockout. |
| Weak passwords | Only a length rule (8-128). Common passwords such as `12345678` are accepted. |
| No email verification | Anyone can register with any address. |
| Email and password changes | Email cannot be changed; there is no "change password" while logged in (use the reset flow). |
| Admin management | Admins can be created only with the command line; there is no screen to promote or remove them. |
| Book deletion | Not offered, to protect history; retire a title by setting total copies to 0. |
| ISBN | Format is checked, the check digit is not. |
| Cover images | `https://` links only, loaded from other sites (they can disappear; the default cover is then shown). No uploads. |
| Overdue members | Not blocked from borrowing; no fines. |
| Low-stock threshold | A constant (2) in code, not editable in the interface. |
| Bonus features | Fines, reservations, ratings, recently viewed and recommendations are not built. |

## Technical limits
| Item | Detail |
|---|---|
| SQLite | One writer at a time (borrows are serialised: correct, but not parallel). WAL mode is on. Fine for a small library; use PostgreSQL with row-level locking for scale. No load test was run. |
| Time | Due dates and "overdue" use one configured timezone (default Asia/Kolkata). |
| Dates | Shown in ISO format (2026-11-18). |
| Audit trail | Admin changes to books are not logged. |
| Security review | Reviewed by the AI assistant and covered by regression tests; not penetration-tested, dependencies not scanned. |

## Known rough edges
| Item | Detail |
|---|---|
| Stale tab across login/logout | A page left open while the same browser signs in or out in another tab shows a "Request not accepted" page when its form is submitted. The page now explains why and nothing is changed; reload and retry. |
| One session per browser | All tabs of one browser share one session cookie, so two users need two browsers, a private window, or `localhost` vs `127.0.0.1`. |
| Terminal pauses on click (Windows) | Clicking inside the Command Prompt running the server pauses it until Enter or Esc is pressed (QuickEdit mode). See the README troubleshooting table. |
| Multiple tabs | Tested by repeating requests from stale pages, which is what a second tab does; manual steps for real browsers are in `TEST_CASES.md` (F7) and have not been run. |
| Manual edits to the database | `total_copies` and `available_copies` are kept consistent by the application and CHECK constraints; editing the file by hand can still desynchronise them. |

## Findings from the code review that are fixed
All nine confirmed problems (public default secret key, login timing leak, missing input limits, misleading database error message, loan that could not be returned after a clock change, missing security headers, search wildcards, login redirect to a POST-only URL, user lookup for static files) have been fixed and each has a regression test in `tests/test_security_fixes.py`.
