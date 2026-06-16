"""SQLAlchemy 引擎 + Session 工厂。"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

log = logging.getLogger(__name__)

# 同步引擎（爬虫是 IO 密集型，同步 psycopg2/psycopg3 足够）
# Windows 上 `localhost` 会被解析为 IPv6 `::1`，而 Postgres 默认只监听 IPv4，
# 因此强制走 127.0.0.1。
_DB_USER = os.getenv("POSTGRES_USER", "starmap")
_DB_PASS = quote_plus(os.getenv("POSTGRES_PASSWORD", "starmap123456"))
_DB_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
_DB_PORT = os.getenv("POSTGRES_PORT", "5432")
_DB_NAME = os.getenv("POSTGRES_DB", "starmap")

_DATABASE_URL = f"postgresql+psycopg://{_DB_USER}:{_DB_PASS}@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"

engine = create_engine(
    _DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_jd_raw_session() -> Iterator[Session]:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


@contextmanager
def get_compliance_session() -> Iterator[Session]:
    """与 jd_raw 同一 session 工厂，复用连接池。"""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


__all__ = ["engine", "SessionLocal", "get_jd_raw_session", "get_compliance_session"]
