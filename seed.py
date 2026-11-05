"""Create or upgrade the tables and load sample books:  python seed.py"""
from app import create_app
from app.db import get_db, init_db

OL = "https://covers.openlibrary.org/b/isbn/{}-L.jpg"

# title, author, isbn, genre, cover_url, total, available, description
BOOKS = [
    ("Clean Code", "Robert C. Martin", "9780132350884", "Programming", OL.format("9780132350884"), 4, 3,
     "A practical guide to writing readable, maintainable code, with examples of refactoring messy programs."),
    ("The Pragmatic Programmer", "Andrew Hunt, David Thomas", "9780135957059", "Programming", OL.format("9780135957059"), 3, 3,
     "Habits and techniques for working as a professional software developer, from design to daily practice."),
    ("Python Crash Course", "Eric Matthes", "9781593279288", "Programming", None, 5, 2,
     "A hands-on introduction to Python through projects including a game, a data visualisation and a web app."),
    ("Atomic Habits", "James Clear", "9780735211292", "Self-Help", OL.format("9780735211292"), 6, 6,
     "How small daily changes compound into lasting habits, with a framework for building good ones and breaking bad ones."),
    ("Deep Work", "Cal Newport", "9781455586691", "Self-Help", None, 2, 0,
     "Argues that focused, distraction-free work is increasingly valuable and shows how to train for it."),
    ("Sapiens", "Yuval Noah Harari", "9780062316097", "History", None, 3, 1,
     "A sweeping history of humankind, from early foragers to the modern era."),
    ("1984", "George Orwell", "9780451524935", "Classic", OL.format("9780451524935"), 4, 4,
     "A dystopian novel about surveillance, propaganda and the loss of truth under a totalitarian state."),
    ("Pride and Prejudice", "Jane Austen", "9780141439518", "Classic", None, 3, 3,
     "A comedy of manners in which Elizabeth Bennet and Mr Darcy have their pride and first impressions tested."),
    ("To Kill a Mockingbird", "Harper Lee", "9780061120084", "Fiction", None, 3, 2,
     "A coming-of-age story about justice and prejudice in the American South, told through a young girl's eyes."),
    ("The Alchemist", "Paulo Coelho", "9780062315007", "Fiction", None, 4, 4,
     "A shepherd boy travels in search of treasure and learns about following his personal calling."),
    ("Dune", "Frank Herbert", "9780441013593", "Science Fiction", None, 2, 1,
     "A desert planet, a prized resource and a noble family's fight for survival in a far-future empire."),
    ("The Hobbit", "J.R.R. Tolkien", "9780547928227", "Fantasy", None, 3, 0,
     "Bilbo Baggins joins a company of dwarves on a quest to reclaim a treasure guarded by a dragon."),
    ("Thinking, Fast and Slow", "Daniel Kahneman", "9780374533557", "Psychology", None, 2, 2,
     "Explores the two systems that drive our thinking and the biases that shape our judgments."),
]

app = create_app()
with app.app_context():
    init_db()
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM books").fetchone()[0]:
        print("Books already exist - nothing to do.")
    else:
        db.executemany(
            "INSERT INTO books (title, author, isbn, category, cover_url, total_copies, "
            "available_copies, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", BOOKS)
        print(f"Added {len(BOOKS)} books.")
