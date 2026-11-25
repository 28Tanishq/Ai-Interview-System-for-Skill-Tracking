"""Load the example dataset into the configured database.

Usage: python -m scripts.load_sample_data
Creates the demo accounts (alice, bob, carol, dave, eve) with password from DEMO_PASSWORD (default Demo@123).
"""
from core import auth, dataset
from core import database as db

if __name__ == "__main__":
    db.init_db()
    auth.ensure_admin()
    res = dataset.load_sample()
    print(f"Database: {db.safe_url()}")
    print(f"Imported {res['users']} users, {res['interviews']} interviews, {res['answers']} answers "
          f"({res['skipped_interviews']} duplicates skipped).")
