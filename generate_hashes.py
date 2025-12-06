"""
Script to generate SHA-256 password hashes for Users.csv
Run this once to hash the demo passwords properly.
Compatible with Python 3.13+
"""

import hashlib

def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

# Generate hashes for demo accounts
admin_hash = hash_password("admin123")
judge_hash = hash_password("hackathon2024")

print("Generated Password Hashes (SHA-256):")
print("=" * 60)
print(f"admin123 -> {admin_hash}")
print(f"hackathon2024 -> {judge_hash}")
print("=" * 60)
print("\nCSV Format (copy-paste ready):")
print(f'1,Admin,User,admin,admin@akinchan.com,{admin_hash}')
print(f'2,Judge,Hackathon,judge,judge@hackathon.com,{judge_hash}')
print("=" * 60)
print("\nCopy these lines to data/Users.csv")
