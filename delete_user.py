import sqlite3
import argparse
import os

# --- Configuration ---
DB_FILE = "users.db"

def delete_user(username):
    """Deletes a user from the database."""
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file '{DB_FILE}' not found.")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # Check if the user exists before deleting
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        if not user:
            print(f"Error: User '{username}' not found.")
            return
        
        # Prevent deleting the last admin user
        if username.lower() == 'admin':
            c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            admin_count = c.fetchone()[0]
            if admin_count <= 1:
                print("Error: Cannot delete the last admin user.")
                return

        c.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()

        # Verify deletion
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        if c.fetchone() is None:
            print(f"User '{username}' deleted successfully.")
        else:
            print(f"Error: Failed to delete user '{username}'.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete a user from the KSV-10 database.")
    parser.add_argument("--username", required=True, help="The username of the user to delete.")
    args = parser.parse_args()

    # Add a confirmation step
    confirm = input(f"Are you sure you want to permanently delete the user '{args.username}'? [y/N]: ")
    if confirm.lower() == 'y':
        delete_user(args.username)
    else:
        print("Operation cancelled.")
