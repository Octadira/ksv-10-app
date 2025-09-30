import sqlite3
import os

# --- Configuration ---
DB_FILE = "users.db"

def list_users():
    """Lists all users in the database."""
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file '{DB_FILE}' not found.")
        print("Please run 'create_admin.py' first to initialize the database.")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT id, username, role FROM users ORDER BY username")
        users = c.fetchall()

        if not users:
            print("No users found in the database.")
            return

        print(f"--- Users in '{DB_FILE}' ---")
        print(f"{'ID':<5} {'Username':<25} {'Role':<10}")
        print("-" * 42)
        for user in users:
            print(f"{user['id']:<5} {user['username']:<25} {user['role']:<10}")
        print("-" * 42)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    list_users()
