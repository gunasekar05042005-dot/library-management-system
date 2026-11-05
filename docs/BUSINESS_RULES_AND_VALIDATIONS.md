# Business rules and validations

## 1. Business rules

| Rule | Description | Enforced by | Tests |
|---|---|---|---|
| BR-01 | A member can borrow only available books | Conditional `UPDATE books SET available_copies = available_copies - 1 WHERE id = ? AND available_copies > 0`, row count checked; `CHECK (available_copies >= 0)`; UI hides the button | `test_book_with_no_copies_rejected`, `test_unavailable_book_cannot_be_borrowed_even_with_a_forged_request` |
| BR-02 | Borrowing reduces and returning increases available copies | Same transaction as the loan insert / loan close | `test_borrow_reduces_copies...`, `test_return_marks_loan_returned_and_restores_copy` |
| BR-03 | A member holds at most 3 books at a time | Count of active loans inside the locked transaction | `test_fourth_book_rejected`, `test_three_book_limit_holds_under_simultaneous_requests` |
| BR-04 | Loan period is 14 days; after that the status is Overdue | `due_date = borrow date + 14 days` (`LOAN_DAYS`); Overdue is derived: not returned and `due_date < today` | `test_borrow_reduces_copies...`, `test_history_shows_all_three_statuses...` |
| BR-05 | Members see only their own history | Queries always filter by the session's user id; the id is never taken from the URL | `test_history_shows_all_three_statuses_and_only_own_records`, `test_history_cannot_be_pointed_at_another_member` |
| BR-06 | Only administrators add or edit books | `@admin_required` on every book-management route | `test_member_cannot_add_or_edit_books_even_with_a_forged_post` |

## 2. Validations

### Users
| Field | Rule | Message |
|---|---|---|
| Full name | Required, at most 100 characters | "Full name is required." / "...at most 100 characters." |
| Email | Required, valid format, at most 254 characters, unique (case-insensitive) | "Email is required." / "Enter a valid email address." / "An account with this email already exists." |
| Password | Required, 8 to 128 characters, must match confirmation | "Password is required." / "...at least 8 characters." / "Passwords do not match." |
| Phone (profile) | Optional; 7-20 digits, spaces, dashes, optional leading + | "Enter a valid phone number..." |
| Role | Never taken from a form; registration always creates a member; admins only via the `create-admin` command | n/a |

### Books (admin form, plus database constraints)
| Field | Rule |
|---|---|
| Title, author, genre | Required; at most 200 / 150 / 50 characters |
| ISBN | Required, 10 or 13 characters (digits; last character of a 10-digit ISBN may be X), hyphens/spaces ignored, **unique** (database `UNIQUE` plus a friendly message) |
| Total copies | Whole number, **not negative**, at most 10000; **cannot be lower than the number currently borrowed** |
| Available copies | Never set by hand: new books start with all copies available; on edit it is recalculated as total minus borrowed; database `CHECK (available_copies <= total_copies)` and `>= 0` |
| Cover image | Optional; must be an `https://` link (500 characters at most); empty means the default image is shown |
| Description | Optional; at most 2000 characters |

### Borrowing
| Rule | Message |
|---|---|
| Book must exist | "That book does not exist." |
| No second active loan of the same book | "You have already borrowed this book." (also a database partial unique index) |
| Fewer than 3 active loans | "You can borrow at most 3 books at a time. Return one before borrowing another." |
| A copy must be available | "No copies of this book are available right now." |
| A returned book cannot be returned again | "This book has already been returned." |
| Only your own loan can be returned | "Borrowing record not found." (same answer as for an ID that does not exist) |

## 3. Calculations
- **Due date** = borrow date + 14 days (calendar days, in the library timezone).
- **Overdue** = not returned and `due_date < today`. A loan due today is not yet overdue.
- **Available copies after edit** = new total copies - copies currently borrowed.
- **Low availability** = books with total copies > 0 and available copies <= 2.
- **Status** (history) = Returned if `returned_at` is set; else Overdue if `due_date < today`; else Borrowed.
- **Return date** is never earlier than the borrow date (protects against clock changes).

## 4. Edge cases required by the brief

| Scenario | Expected behaviour | Handling | Test |
|---|---|---|---|
| Two members borrow the last copy at the same time | One succeeds, the other sees an error | `BEGIN IMMEDIATE` serialises borrows; conditional update | `test_two_members_cannot_borrow_the_last_copy` |
| Member refreshes while borrowing | Not borrowed twice | Redirect after POST; duplicate loan refused | `test_refreshing_after_borrowing_does_not_borrow_again` |
| Returning an already returned book | Rejected | Conditional update `... AND returned_at IS NULL` | `test_book_cannot_be_returned_twice`, `test_double_submit_returns_the_copy_only_once` |
| Admin reduces total copies below the borrowed count | Rejected | Checked inside a locked transaction | `test_total_copies_cannot_drop_below_the_borrowed_count`, `test_edit_and_borrow_racing_never_break_the_copy_counts` |
| Multiple browser tabs | Data stays consistent | Every rule is checked on the server at the moment of the request, so a stale page cannot bypass it | `test_stale_return_tab_cannot_return_twice`, `test_stale_borrow_page_after_another_member_takes_the_last_copy` |
