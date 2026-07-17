"""Check what postgres_uri the running config resolves to."""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from app.config import settings

print("postgres_uri:", settings.postgres_uri)
print("postgres_host:", settings.postgres_host)
print("postgres_port:", settings.postgres_port)
print("postgres_user:", settings.postgres_user)
print("postgres_db:", settings.postgres_db)
print("postgres_sslmode:", settings.postgres_sslmode)
print("postgres_password set:", bool(settings.postgres_password))
print("postgres_password length:", len(settings.postgres_password) if settings.postgres_password else 0)