"""Backend ``app.db`` package — shared SQLAlchemy primitives.

Currently exports ``get_async_engine`` and ``get_session_factory`` via
``app.db.session``. Kept as a package so future shared ORM types (Base, NamingConvention,
etc.) can live here without forcing callers to import from a module path that implies a
specific engine.
"""
from app.db.session import get_async_engine, get_session_factory

__all__ = ["get_async_engine", "get_session_factory"]
