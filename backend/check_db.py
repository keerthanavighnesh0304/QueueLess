"""
QueueLess Safe MySQL Connection Diagnostic Tool

Tests MySQL connection parameters from backend/.env without ever printing passwords or secrets.
"""

import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings, BACKEND_DIR
from app.database import check_database_connection


def run_diagnostic():
    print("=" * 60)
    print("QueueLess: MySQL Database Connection Diagnostic")
    print("=" * 60)

    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        print(f"\n[ERROR] Configuration file '{env_path}' not found.")
        print("Please copy 'backend/.env.example' to 'backend/.env' and fill in your local MySQL settings.")
        sys.exit(1)

    print(f"[INFO] Configuration file detected at: {env_path}")
    print(f"[INFO] Target Host:     {settings.DB_HOST}:{settings.DB_PORT}")
    print(f"[INFO] Target User:     {settings.DB_USER}")
    print(f"[INFO] Target Database: {settings.DB_NAME}")
    print("[INFO] Testing connection to MySQL server...")

    success, message = check_database_connection()

    if success:
        print("\n" + "=" * 60)
        print("[SUCCESS] MySQL server and database connection verified!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("[FAILED] Could not connect to MySQL.")
        print(f"Details: {message}")
        print("=" * 60)

        # Helpful hints for common errors
        if "1049" in message or "Unknown database" in message:
            print("\n[NOTE] MySQL server is running, but the database 'queueless_db' does not exist yet.")
            print("Please create it using your local MySQL client:")
            print("    CREATE DATABASE IF NOT EXISTS queueless_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        elif "1045" in message or "Access denied" in message:
            print("\n[NOTE] Access denied for the configured username/password.")
            print("Please check the DB_USER and DB_PASSWORD values in 'backend/.env'.")
        elif "2003" in message or "Can't connect to MySQL server" in message:
            print("\n[NOTE] Could not reach MySQL server. Please ensure MySQL service is running on your machine.")

        sys.exit(1)


if __name__ == "__main__":
    run_diagnostic()
