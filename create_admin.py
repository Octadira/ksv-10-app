import sqlite3
from passlib.context import CryptContext
import os

# --- Configuration ---
DB_FILE = "users.db"
ADMIN_USERNAME = "admin"
# WARNING: This is a default password. Change it in a secure way.
ADMIN_PASSWORD = "admin"

# --- Hashing setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    """Hashes the password."""
    return pwd_context.hash(password)

def create_database():
    """Creates the database and the users table if they don't exist."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Use IF NOT EXISTS to prevent errors on subsequent runs
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'user'))
            )
        ''')
        conn.commit()
        print(f"Database '{DB_FILE}' and table 'users' are ready.")
    except sqlite3.Error as e:
        print(f"Database error during table creation: {e}")
    finally:
        if conn:
            conn.close()

def add_admin_user():
    """Adds the initial admin user to the database if they don't exist."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # Check if the admin user already exists
        c.execute("SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,))
        if c.fetchone():
            print(f"Admin user '{ADMIN_USERNAME}' already exists. No action taken.")
            return

        # If not, create the admin user
        password_hash = get_password_hash(ADMIN_PASSWORD)
        c.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (ADMIN_USERNAME, password_hash, 'admin')
        )
        conn.commit()
        print(f"Admin user '{ADMIN_USERNAME}' created successfully.")
        print("IMPORTANT: The default password is 'admin'. Please change this in a production environment.")

    except sqlite3.Error as e:
        print(f"Database error during admin user creation: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("--- Initializing User Database ---")
    create_database()
    add_admin_user()
    print("--- Initialization Complete ---")
