# Library Management System

## Run
    python -m venv venv
    source venv/bin/activate        # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    python seed.py                  # creates instance/library.sqlite + sample books
    flask --app app create-admin    # prompts for name, email, password
    flask --app app run --debug     # open http://127.0.0.1:5000

## Test
    python -m pytest
