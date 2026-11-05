# Test cases and expected results

Run all automated tests: `python -m pytest` (141 tests). "Auto" = automated test in `tests/`; "Manual" = steps for a real browser.
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

## J. Catalogue and search

| ID | Test | Expected result | Type |
|---|---|---|---|
| J1 | Search by title (any capitalisation) | Matching books only | Auto: `test_search_by_title_is_case_insensitive` |
| J2 | Search by author | Matching books only | Auto: `test_search_by_author` |
| J3 | Filter by genre; combine with search; "Available now" | Only matching books; unavailable ones hidden | Auto: `test_filter_by_genre`, `test_search_and_genre_combine`, `test_available_now_filter_hides_books_with_no_copies` |
| J4 | No match | "No books match your search." | Auto: `test_no_match_shows_a_friendly_message` |
| J5 | Search for `%` or `_` | Treated as ordinary characters, not wildcards | Auto: `test_percent_and_underscore_are_searched_literally` |
| J6 | 30 books | 12 per page, pager shown, bad page numbers clamped | Auto: `test_catalog_is_paginated_and_clamps_bad_page_numbers` |
| J7 | Open details | Description, copies and default cover shown; no inline script handlers | Auto: `test_details_page_shows_description_and_default_cover` |

## K. Borrowing history and profile

| ID | Test | Expected result | Type |
|---|---|---|---|
| K1 | History with a late, a returned and a current loan | Statuses Overdue, Returned, Borrowed shown; status tabs filter correctly | Auto: `test_history_shows_all_three_statuses_and_only_own_records` |
| K2 | Another member's loans (including `?user_id=` tampering) | Never visible | Auto: same test, `test_history_cannot_be_pointed_at_another_member` |
| K3 | 20 loans | 15 per page, pager works | Auto: `test_history_is_paginated` |
| K4 | History as anonymous / admin | Login redirect / 403 | Auto: `test_history_requires_a_member` |
| K5 | Update name and phone | Saved and shown | Auto: `test_profile_view_and_update` |
| K6 | Blank or too-long name, bad phone | Specific message; nothing saved | Auto: `test_profile_validation_rejects_bad_input_and_changes_nothing` |
| K7 | Try to change email or role through the form | Ignored | Auto: `test_profile_cannot_change_email_or_role` |
| K8 | Clear the phone | Stored as empty | Auto: `test_blank_phone_clears_the_phone_number` |

## L. Password reset

| ID | Test | Expected result | Type |
|---|---|---|---|
| L1 | Request a link for a registered email | Neutral message; link logged (and shown in demo mode) | Auto: `test_known_email_gets_a_link_and_it_is_logged` |
| L2 | Request for an unknown email | Identical message, no link (no account enumeration) | Auto: `test_unknown_email_gets_the_same_message_and_no_link` |
| L3 | Use the link, set a new password | Old password stops working, new one works | Auto: `test_reset_changes_the_password` |
| L4 | Use the same link twice | Second use refused | Auto: `test_link_can_only_be_used_once` |
| L5 | Expired or tampered link | Refused | Auto: `test_expired_link_is_rejected`, `test_tampered_link_is_rejected` |
| L6 | Short or mismatched new password | Message; password unchanged | Auto: `test_weak_or_mismatched_new_password_is_refused` |
| L7 | Someone is logged in elsewhere when the password is reset | That session is ended | Auto: `test_reset_signs_out_existing_sessions` |

## M. Administration

| ID | Test | Expected result | Type |
|---|---|---|---|
| M1 | Member or visitor opens admin pages / posts a book | 403 / login redirect; nothing created or changed (BR-06) | Auto: `test_admin_pages_need_an_admin`, `test_member_cannot_add_or_edit_books_even_with_a_forged_post` |
| M2 | Admin adds a valid book | Created with all copies available; appears in the catalogue | Auto: `test_admin_adds_a_book_with_every_copy_available` |
| M3 | Each invalid field (blank, bad ISBN, negative or non-numeric copies, over-long text, non-https cover) | Specific message; no book created | Auto: `test_invalid_book_data_is_rejected` (15 cases) |
| M4 | Duplicate ISBN (also with hyphens) | "already exists"; one book | Auto: `test_isbn_must_be_unique` |
| M5 | Edit total copies up, down to the borrowed count, below it | Available recalculated; below the borrowed count rejected and nothing changed | Auto: `test_total_copies_cannot_drop_below_the_borrowed_count` |
| M6 | Edit and borrow at the same instant | Counts never inconsistent | Auto: `test_edit_and_borrow_racing_never_break_the_copy_counts` |
| M7 | Edit ISBN to another book's / keep own | Refused / allowed | Auto: `test_edit_checks_isbn_against_other_books_only` |
| M8 | Members list, borrowings list and filters | Members only (no admins), counts correct, filters work | Auto: `test_members_list_shows_members_only_with_counts`, `test_borrowings_list_filters_and_names_the_member` |

## N. Regression tests for the code-review findings
| ID | Finding | Test |
|---|---|---|
| N1 | Public default secret key | `test_cookie_signed_with_the_old_public_default_key_is_useless`, `test_secret_key_is_random_and_stable_between_runs`, `test_even_a_cookie_signed_with_the_real_key_needs_the_password_fingerprint` |
| N2 | Login timing leak | `test_a_password_hash_is_checked_whether_or_not_the_email_exists` |
| N3 | No input limits | `test_overlong_name_and_email_are_rejected`, `test_oversized_request_body_is_refused` |
| N4 | Misleading database error | `test_a_genuine_database_fault_is_not_reported_as_already_borrowed` |
| N5 | Loan that cannot be returned | `test_return_never_writes_a_date_before_the_borrow_date` |
| N6 | Headers and cookie flags | `test_security_headers_are_sent`, `test_session_cookie_flags` |
| N7 | `next` after a POST | `test_only_page_views_are_resumed_after_login` |
| N8 | Static files hit the database | `test_static_files_do_not_query_the_user_table` |
| N9 | Old databases, timezone, defaults | `test_old_databases_are_upgraded`, `test_today_uses_the_configured_timezone`, `test_reset_link_is_hidden_unless_demo_mode_is_on` |

## Known issues
See `docs/KNOWN_ISSUES.md`.
