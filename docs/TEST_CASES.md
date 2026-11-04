# Test cases and expected results

Run all automated tests: `python -m pytest` (59 tests). "Auto" = automated test in `tests/`; "Manual" = steps for a real browser.
Test data: one admin (`admin@test.com`), members created per test, books with the copy counts stated.

## A. Authentication

| ID | Test | Steps | Expected result | Type |
|---|---|---|---|---|
| A1 | Register (valid) | Submit a valid name, email, 8+ char password | Account created with role `member`; password stored as a hash, never plain text; redirect to login | Auto: `test_register_creates_member_with_hashed_password` |
| A2 | Duplicate email | Register `member@test.com` twice | Second attempt refused: "An account with this email already exists." No second user | Auto: `test_duplicate_email_rejected_case_insensitive` |
| A3 | Duplicate email, different case | Register `MEMBER@test.com` after `member@test.com` | Refused as a duplicate (email is case-insensitive) | Auto: same test |
| A4 | Short password | Password of 7 characters | "Password must be at least 8 characters."; no user created | Auto: `test_invalid_registration_is_rejected` |
| A5 | Minimum length accepted | Password of exactly 8 characters | Account created | Auto: `test_password_of_exactly_minimum_length_is_accepted` |
| A6 | Password too long | Password of 129 characters | "Password must be at most 128 characters."; no user created | Auto: `test_invalid_registration_is_rejected` |
| A7 | Passwords differ | Confirmation does not match | "Passwords do not match." | Auto: `test_mismatched_passwords_rejected` |
| A8 | Blank name / bad email | Name of spaces; `not-an-email`; `a@b` | Specific validation message; no user created | Auto: `test_invalid_registration_is_rejected` |
| A9 | Self-register as admin | Add a hidden field `role=admin` to the form | Field ignored; user is a `member` | Auto: `test_cannot_register_as_admin` |
| A10 | Invalid login: wrong password | Correct email, wrong password | "Invalid email or password."; not logged in | Auto: `test_invalid_logins_get_one_generic_error` |
| A11 | Invalid login: unknown email | Unregistered email | Same generic message (does not reveal whether the email exists) | Auto: same test |
| A12 | Invalid login: empty form / empty password | Submit blanks | Same generic message | Auto: same test |
| A13 | Invalid login: SQL injection | Email and password `' OR '1'='1` | Same generic message; no error page; not logged in | Auto: same test |
| A14 | Login email case | Log in as `MEMBER@Test.com` | Login succeeds | Auto: `test_login_email_is_case_insensitive` |
| A15 | Logout | POST /logout | Session cleared; GET /logout returns 405 | Auto: `test_logout_requires_post_and_clears_session` |
| A16 | Open redirect | Log in with `next=//evil.com` | Redirected to the catalog, not the external site | Auto: `test_login_ignores_external_redirect` |

## B. Access control

| ID | Test | Expected result | Type |
|---|---|---|---|
| B1 | Anonymous opens /books, /dashboard or posts to /borrow | Redirect to login | Auto: `test_anonymous_user_redirected_to_login` |
| B2 | Member opens /admin/ | 403 Access denied | Auto: `test_member_blocked_from_admin_but_admin_allowed` |
| B3 | Admin opens /dashboard, borrows or returns | 403 (member-only actions) | Auto: `test_each_dashboard_is_restricted_to_its_role`, `test_admin_cannot_borrow_and_anonymous_is_redirected` |
| B4 | POST without CSRF token | 400; nothing changes | Auto: `test_csrf_blocks_post_without_token` |
| B5 | Member returns another member's loan | "Borrowing record not found."; the owner's loan stays active | Auto: `test_member_cannot_return_another_members_loan` |
| B6 | Member dashboard shows another member's books | Never: only own loans appear | Auto: `test_member_dashboard_shows_only_own_loans_and_overdue` |

## C. Borrowing

| ID | Test | Steps | Expected result | Type |
|---|---|---|---|---|
| C1 | Borrow (valid) | Borrow a book with 3 copies on 2026-11-04 | Available copies 2; loan row created; due date 2026-11-18 (14 days) | Auto: `test_borrow_reduces_copies_and_sets_14_day_due_date` |
| C2 | Unavailable book | Book with 0 available copies | No Borrow button, notice "No copies are available right now."; a forged POST gets "No copies of this book are available"; no loan; copies stay 0 | Auto: `test_unavailable_book_cannot_be_borrowed_even_with_a_forged_request` |
| C3 | Third book allowed, fourth blocked | Borrow 3 different books, then a 4th | 4th refused: "You can borrow at most 3 books at a time."; page shows "the maximum" notice; 3 loans; 4th book's copies unchanged | Auto: `test_fourth_book_is_blocked_in_ui_and_by_forged_request`, `test_fourth_book_rejected` |
| C4 | Duplicate borrowing | Borrow the same book twice while still borrowed | "You have already borrowed this book."; copies reduced once; one loan | Auto: `test_same_book_cannot_be_borrowed_twice` |
| C5 | Borrow again after returning | Return a book, borrow it again | Allowed | Auto: `test_same_book_can_be_borrowed_again_after_return` |
| C6 | Nonexistent book | POST /borrow/9999 | "That book does not exist." on a 404 page | Auto: `test_borrowing_a_book_that_does_not_exist` |

## D. Returning

| ID | Test | Steps | Expected result | Type |
|---|---|---|---|---|
| D1 | Return (valid) | Return a borrowed book | `returned_at` set (row kept for history); available copies +1 | Auto: `test_return_marks_loan_returned_and_restores_copy` |
| D2 | Returning twice | Return the same loan again | "This book has already been returned."; copies increased only once | Auto: `test_book_cannot_be_returned_twice` |
| D3 | Return unknown ID | POST /return/9999 | "Borrowing record not found." | Auto: `test_unknown_borrowing_id_rejected` |
| D4 | Overdue return | Loan past its due date | Shown as Overdue on the dashboard; return still allowed | Auto: `test_dashboard_page_return_flow_and_overdue_flag` |
| D5 | Return is POST-only | GET /return/1 | 405 | Auto: `test_return_route_is_post_only_and_members_only` |

## E. Simultaneous requests

| ID | Test | Steps | Expected result | Type |
|---|---|---|---|---|
| E1 | Last copy | 6 members borrow the only copy at the same instant | Exactly 1 succeeds, 5 get "No copies available"; copies 0; 1 loan | Auto: `test_two_members_cannot_borrow_the_last_copy` |
| E2 | Double click | One member sends 5 borrow requests for one book at once | 1 loan, copies reduced by 1, others "already borrowed" | Auto: `test_double_click_by_one_member_borrows_once` |
| E3 | Limit race | One member borrows 6 different books at once | Exactly 3 succeed, 3 refused; 3 loans | Auto: `test_three_book_limit_holds_under_simultaneous_requests` |
| E4 | Double return | 5 simultaneous returns of one loan | 1 succeeds, 4 refused; copies back to total, never above | Auto: `test_double_submit_returns_the_copy_only_once` |

## F. Browser refresh and multiple tabs

| ID | Test | Steps | Expected result | Type |
|---|---|---|---|---|
| F1 | Refresh after borrowing | Borrow, then refresh the page 3 times | Borrow response is a redirect, so refreshing is a harmless GET; 1 loan, copies reduced once | Auto: `test_refreshing_after_borrowing_does_not_borrow_again` |
| F2 | Resubmit the form | Re-send the borrow POST ("Confirm form resubmission") | "You have already borrowed this book."; no extra loan or copy change | Auto: same test |
| F3 | Refresh the dashboard | Reload /dashboard repeatedly | Same data every time; nothing changes | Auto: `test_refreshing_the_dashboard_changes_nothing` |
| F4 | Two tabs, return | Return in tab A, then click the stale Return button in tab B | Tab B: "This book has already been returned."; copies +1 once | Auto: `test_stale_return_tab_cannot_return_twice` |
| F5 | Two browsers, last copy | Member 2 loads the book page, member 1 borrows the last copy, member 2 clicks the stale Borrow button | Member 2: "No copies of this book are available"; 1 loan | Auto: `test_stale_borrow_page_after_another_member_takes_the_last_copy` |
| F6 | Logout in one tab | Tab A logs out, tab B clicks Borrow | Rejected with 400 (security token no longer valid); no loan | Auto: `test_stale_tab_is_rejected_after_logout_in_another_tab` |
| F7 | Real browser, two tabs | Manual: open one book in two tabs and click Borrow in both | Second tab shows the "already borrowed" message; copies reduced once | Manual |

## G. Database constraints (last line of defence)

| ID | Test | Expected result | Type |
|---|---|---|---|
| G1 | Insert a book with negative copies / available above total | `IntegrityError` | Auto: `test_database_rejects_invalid_rows` |
| G2 | Insert a user with an invalid role / duplicate email in other case | `IntegrityError` | Auto: same test |
| G3 | Insert a loan for a user and book that do not exist | `IntegrityError` (foreign keys are enforced) | Auto: same test |
| G4 | Insert a second active loan of the same book for one member | `IntegrityError` (partial unique index) | Auto: `test_database_rejects_a_second_active_loan_of_the_same_book` |

## H. Dashboards

| ID | Test | Expected result | Type |
|---|---|---|---|
| H1 | Admin figures | Members exclude admins; books, copies, active and overdue loans and low-stock list match the data; update after a return | Auto: `test_admin_stats_are_calculated_from_real_data` |
| H2 | Low availability | Books with 2 or fewer copies available are listed; retired books (0 copies owned) are not | Auto: same test |
| H3 | Member dashboard | Shows "1 of 3", due dates, Overdue badge for late loans | Auto: `test_member_dashboard_shows_only_own_loans_and_overdue` |

## I. Manual UI checks

| ID | Check | Expected result |
|---|---|---|
| I1 | Catalog at 375 px wide | Cards reflow, no horizontal scrolling, forms usable |
| I2 | Book with no cover or a broken cover URL | Default cover image is shown |
| I3 | Search "clean", filter genre, tick "Available now" | Results narrow correctly; "No books match" message when empty |
| I4 | Keyboard only | Every control reachable with Tab and has a visible focus outline |

## J. Pending (features not built yet, so no tests)
Borrowing history page (member sees own records only), profile view/update, admin add/edit books, admin member and borrowing lists.

## Known issues
- A stale tab left open across login or logout shows a "400 Request not accepted" page instead of a friendlier message.
- No login rate limiting; no password reset.
- SQLite allows one writer at a time, so borrows are serialised (correct, but not parallel).
