# Assumptions and ambiguous requirements

## 1. The three ambiguous requirements in the brief

### Can a member borrow books without completing their profile?
**Decision: yes.** Registration collects only what is needed to identify and secure the account: name, email and password. Phone number is optional and the profile page only lets members update name and phone.
**Reason:** a library loan needs an identified member, not a complete profile. Forcing extra fields before borrowing adds friction without protecting any rule in the brief.
**If the library wanted otherwise:** add the required fields to the registration or profile validation and check them at the start of `borrow_book`.

### Should membership have an expiry date?
**Decision: no expiry.** The brief lists no renewal flow, fee or status for memberships, so adding one would invent features.
**If needed:** add a nullable `membership_expires_at` column to `users`, check it inside `borrow_book` (reject with "Your membership has expired"), and let admins extend it on the member list.

### Can an administrator also borrow books as a member?
**Decision: no.** An admin account is for running the library; borrow and return return "403 Access denied" for admins. Roles are mutually exclusive, which also keeps the member statistics (members, active loans) unambiguous.
**Alternative:** an administrator who wants to borrow registers a separate member account with another email address.

## 2. Other assumptions

| Topic | Assumption |
|---|---|
| Loan period | 14 calendar days from the borrow date, computed in the library timezone (default Asia/Kolkata, configurable). A loan due today is not yet overdue. |
| Overdue loans | They still count toward the 3-book limit and the member may still borrow other books; late returns are allowed. No fines (bonus item not built). |
| Statuses | Borrowed, Returned and Overdue are derived from `returned_at` and `due_date`, never stored. |
| "Total books" | The number of titles in the catalogue; the total number of copies is shown beside it. |
| "Low availability" | A book that owns at least one copy and has 2 or fewer available (constant `LOW_STOCK_THRESHOLD`). A title that owns only 2 copies is therefore listed even when both are on the shelf. |
| Genre | A free-text field; the filter lists the genres that exist. |
| Cover image | An `https://` link entered by an admin; no file uploads. Missing or broken images fall back to the default cover. |
| ISBN | Required for books added through the admin form; format (10 or 13 characters) is checked, the check digit is not. |
| Deleting books | Not offered, to protect borrowing history. A retired title is set to 0 total copies. |
| Email | The login identifier; case-insensitive; cannot be changed on the profile page. |
| Passwords | 8 to 128 characters, no composition rules. Stored as salted slow hashes. |
| Password reset | There is no email server. The signed, one-hour, single-use link is written to the server log, and shown on the page only in demo mode (`--debug` or `SHOW_RESET_LINK=1`). Reset signs out existing sessions. |
| Creating admins | Only through `flask --app app create-admin`; nobody can become an admin through the website. |
| Sessions | Last 8 hours from login, end when the password changes. |
| Concurrency | One SQLite database file; writes are serialised, which is what makes the borrow rules correct. |
| Administrator sign-in | A separate page at `/admin/login` accepts only administrator accounts. Administrators can also use the ordinary login and land on the admin dashboard. |
| Database viewer | Administrators can see, read-only, every table: users (members and admins), books and borrowings. Password hashes are never shown and nothing is edited there. |
| Database file | `instance/library.db`, created automatically when the app starts. |
| One session per browser | Tabs of one browser share one signed-in user; a second user needs another browser or a private window. |
