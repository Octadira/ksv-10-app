import sqlite3
from passlib.context import CryptContext
import argparse
import os

# --- Configuration ---
DB_FILE = "users.db"

# --- Hashing setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def add_user(username, password, role):
    """Adds a new user to the database."""
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file '{DB_FILE}' not found.")
        print("Please run 'create_admin.py' first to initialize the database.")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # Check if user already exists
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        if c.fetchone():
            print(f"Error: User '{username}' already exists.")
            return

        password_hash = get_password_hash(password)
        c.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role)
        )
        conn.commit()
        print(f"User '{username}' with role '{role}' created successfully.")

    except sqlite3.IntegrityError:
        print(f"Error: User '{username}' already exists (Integrity Error).")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a new user to the KSV-10 database.")
    parser.add_argument("--username", required=True, help="The username for the new user.")
    parser.add_argument("--password", required=True, help="The password for the new user.")
    parser.add_argument("--role", required=True, choices=['admin', 'user'], help="The role for the new user ('admin' or 'user').")

    args = parser.parse_args()

    add_user(args.username, args.password, args.role)
