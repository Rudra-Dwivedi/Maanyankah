"""
Creates (or promotes an existing user to) an admin account.

Supports interactive input, CLI flags (--username, --password, --email),
or environment variables (ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL).

Usage:
    python create_admin.py
    python create_admin.py --username admin --password secret --email admin@example.com
"""

import argparse
import getpass
import os
import sqlite3

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


def run():
    parser = argparse.ArgumentParser(description="Create or promote an admin account.")
    parser.add_argument("--username", help="Admin username", default=os.environ.get("ADMIN_USERNAME", "Rudra"))
    parser.add_argument("--email", help="Admin email", default=os.environ.get("ADMIN_EMAIL"))
    parser.add_argument("--password", help="Admin password", default=os.environ.get("ADMIN_PASSWORD", "Rudra@8318"))
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        db = get_db()

        username = (args.username or input("Admin username: ")).strip()
        if not username:
            print("Username cannot be empty.")
            return

        existing = db.execute(
            "SELECT id, role FROM users WHERE LOWER(username) = LOWER(?)", (username,)
        ).fetchone()

        if existing:
            new_password = args.password or getpass.getpass(f"New password for admin '{username}': ")
            if new_password:
                db.execute(
                    "UPDATE users SET role = 'admin', password_hash = ? WHERE id = ?",
                    (generate_password_hash(new_password), existing["id"]),
                )
            else:
                db.execute(
                    "UPDATE users SET role = 'admin' WHERE id = ?", (existing["id"],)
                )
            db.commit()
            print(f"Admin account '{username}' updated with new credentials.")
            return

        email = (args.email or input("Admin email: ")).strip() if not args.email else args.email.strip()
        if not email:
            email = f"{username}@fannetwork.local"

        password = args.password or getpass.getpass("Admin password: ")
        if not password:
            print("Password cannot be empty.")
            return

        try:
            db.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
                (username, email, generate_password_hash(password)),
            )
            db.commit()
            print(f"Admin account '{username}' created. Log in at /admin/login.")
        except sqlite3.IntegrityError:
            print("That username or email is already taken.")


if __name__ == "__main__":
    run()
