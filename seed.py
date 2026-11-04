"""Create the tables and load sample books:  python seed.py"""
from app import create_app
from app.db import get_db, init_db

OL = "https://covers.openlibrary.org/b/isbn/{}-L.jpg"

# title, author, isbn, genre, cover_url, total, available
BOOKS = [
    ("Clean Code", "Robert C. Martin", "9780132350884", "Programming", OL.format("9780132350884"), 4, 3),
    ("The Pragmatic Programmer", "Andrew Hunt, David Thomas", "9780135957059", "Programming", OL.format("9780135957059"), 3, 3),
    ("Python Crash Course", "Eric Matthes", "9781593279288", "Programming", None, 5, 2),
    ("Atomic Habits", "James Clear", "9780735211292", "Self-Help", OL.format("9780735211292"), 6, 6),
    ("Deep Work", "Cal Newport", "9781455586691", "Self-Help", None, 2, 0),
    ("Sapiens", "Yuval Noah Harari", "9780062316097", "History", None, 3, 1),
    ("1984", "George Orwell", "9780451524935", "Classic", OL.format("9780451524935"), 4, 4),
    ("Pride and Prejudice", "Jane Austen", "9780141439518", "Classic", None, 3, 3),
    ("To Kill a Mockingbird", "Harper Lee", "9780061120084", "Fiction", None, 3, 2),
    ("The Alchemist", "Paulo Coelho", "9780062315007", "Fiction", None, 4, 4),
    ("Dune", "Frank Herbert", "9780441013593", "Science Fiction", None, 2, 1),
    ("The Hobbit", "J.R.R. Tolkien", "9780547928227", "Fantasy", None, 3, 0),
    ("Thinking, Fast and Slow", "Daniel Kahneman", "9780374533557", "Psychology", None, 2, 2),
]

app = create_app()
with app.app_context():
    init_db()
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM books").fetchone()[0]:
        print("Books already exist - nothing to do.")
    else:
        db.executemany(
            "INSERT INTO books (title, author, isbn, category, cover_url, total_copies, available_copies)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)", BOOKS)
        db.commit()
        print(f"Added {len(BOOKS)} books.")
