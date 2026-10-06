"""
check_connection.py — One-off script to verify the app's DB
connection and credentials are correct before building on top of them.
"""

from app.db import health_check

if __name__ == "__main__":
    if health_check():
        print("✅ Connected successfully as the read-only role.")
    else:
        print("❌ Connection failed. Check .env values.")