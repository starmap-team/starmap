"""Domain exceptions for the service/core layer.

These are raised by service and core modules instead of HTTPException,
keeping business logic decoupled from the web framework. The API layer
maps them to appropriate HTTP responses.
"""
from __future__ import annotations


class StarMapError(Exception):
    """Base exception for all StarMap domain errors."""


class PositionNotFoundError(StarMapError):
    """Raised when a target position is not found in the knowledge graph."""

    def __init__(self, position_name: str) -> None:
        self.position_name = position_name
        super().__init__(f'Position "{position_name}" not found in graph')


class PlanNotFoundError(StarMapError):
    """Raised when a learning plan is not found."""

    def __init__(self, plan_id: str) -> None:
        self.plan_id = plan_id
        super().__init__(f"Plan {plan_id} not found")


class PlanOwnershipError(StarMapError):
    """Raised when a user tries to access a plan they don't own."""

    def __init__(self, plan_id: str, user_id: str) -> None:
        self.plan_id = plan_id
        self.user_id = user_id
        super().__init__(f"User {user_id} does not own plan {plan_id}")
