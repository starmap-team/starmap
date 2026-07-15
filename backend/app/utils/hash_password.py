"""Utility: generate bcrypt hash for AUTH_USERS migration.

Usage:
    python -m app.utils.hash_password <plaintext_password>
    # Output: $2b$12$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy
"""
import sys

import bcrypt


def hash_password(plain: str) -> str:
    """Generate bcrypt hash for a plaintext password (work factor 12)."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.utils.hash_password <plaintext_password>")
        sys.exit(1)
    print(hash_password(sys.argv[1]))
