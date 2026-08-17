"""Admin user-management API.

All endpoints require an authenticated admin (require_admin).
Endpoints:
- GET    /admin/users                       list users (paginated, filterable)
- POST   /admin/users                       create user
- GET    /admin/users/{id}                  detail one user
- PATCH  /admin/users/{id}                  role / is_active / must_change_password / email
- DELETE /admin/users/{id}                  soft-delete (disable)
- POST   /admin/users/{id}/unlock           clear lockout counter
- POST   /admin/users/{id}/reset-password   admin-set new password
- GET    /admin/audit-events                query audit_events
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db_session
from app.models.audit_models import AuditEventRecord
from app.schemas.admin import (
    AdminResetPasswordRequest,
    CreateUserRequest,
    DeleteUserRequest,
    UpdateUserRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/admin", tags=["用户管理(管理员)"])

# ═══════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════


def _require_admin(user: dict[str, Any] = Depends(get_current_user)) -> str:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user.get("sub", "admin")


# ═══════════════════════════════════════════════════════════════
# User CRUD
# ═══════════════════════════════════════════════════════════════


@router.get("/users")
async def list_users(
    session: AsyncSession = Depends(get_db_session),
    actor: str = Depends(_require_admin),
    search: str | None = Query(default=None, description="Substring match on username"),
    role: str | None = Query(default=None, description="admin | user"),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """List users with pagination and filtering."""
    rows, total = await auth_service.list_users(
        session,
        search=search,
        role=role,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [u.to_dict() for u in rows],
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    session: AsyncSession = Depends(get_db_session),
    actor: str = Depends(_require_admin),
) -> dict[str, Any]:
    """Create a new user account."""
    try:
        user = await auth_service.create_user(
            username=body.username,
            password=body.password,
            role=body.role,
            session=session,
            email=body.email,
            actor=actor,
        )
    except auth_service.AuthError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=(
                "邮箱已被使用" if isinstance(exc, auth_service.UsernameTakenError)
                and body.email and body.email in str(exc)
                else str(exc)
            ),
        ) from exc

    if body.must_change_password:
        user.must_change_password = True
        await session.commit()
        await session.refresh(user)

    return user.to_dict()


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    actor: str = Depends(_require_admin),
) -> dict[str, Any]:
    """Fetch a single user by id."""
    user = await auth_service.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user.to_dict()


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    session: AsyncSession = Depends(get_db_session),
    actor: str = Depends(_require_admin),
) -> dict[str, Any]:
    """Update role / is_active / must_change_password / email."""
    try:
        user = await auth_service.update_user(
            user_id,
            session,
            role=body.role,
            is_active=body.is_active,
            must_change_password=body.must_change_password,
            email=str(body.email) if body.email is not None else None,
            actor=actor,
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc

    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user.to_dict()


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    body: DeleteUserRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    actor: str = Depends(_require_admin),
) -> dict[str, Any]:
    """Soft-delete (disable) a user."""
    reason = body.reason if body else None
    deleted = await auth_service.delete_user(
        user_id, session, actor=actor, reason=reason
    )
    if not deleted:
 # Could be not found OR already disabled — disambiguate
        existing = await auth_service.get_user_by_id(session, user_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        raise HTTPException(status_code=409, detail="用户已被禁用")
    return {"deleted": True}


@router.post("/users/{user_id}/unlock")
async def unlock_user(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    actor: str = Depends(_require_admin),
) -> dict[str, Any]:
    """Clear a user's lockout window."""
    user = await auth_service.unlock_user(user_id, session, actor=actor)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user.to_dict()


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str,
    body: AdminResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    actor: str = Depends(_require_admin),
) -> dict[str, Any]:
    """Admin-sets a user's password."""
    try:
        user = await auth_service.reset_password(
            user_id, body.new_password, session, actor=actor
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc

    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user.to_dict()


# ═══════════════════════════════════════════════════════════════
# Audit log query
# ═══════════════════════════════════════════════════════════════


@router.get("/audit-events")
async def list_audit_events(
    session: AsyncSession = Depends(get_db_session),
    actor: str = Depends(_require_admin),
    actor_filter: str | None = Query(default=None, alias="actor"),
    event: str | None = Query(default=None),
    from_ts: datetime | None = Query(default=None),
    to_ts: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Paginated query over the audit_events table.

    All times are treated as UTC. To filter without TZ ambiguity, pass
    ISO-8601 with explicit offset or 'Z'.
    """
    from sqlalchemy import func

    stmt = select(AuditEventRecord)
    count_stmt = select(func.count()).select_from(AuditEventRecord)

    if actor_filter:
        stmt = stmt.where(AuditEventRecord.actor == actor_filter)
        count_stmt = count_stmt.where(AuditEventRecord.actor == actor_filter)
    if event:
        stmt = stmt.where(AuditEventRecord.event == event)
        count_stmt = count_stmt.where(AuditEventRecord.event == event)
    if from_ts:
        if from_ts.tzinfo is None:
            from_ts = from_ts.replace(tzinfo=UTC)
        stmt = stmt.where(AuditEventRecord.created_at >= from_ts)
        count_stmt = count_stmt.where(AuditEventRecord.created_at >= from_ts)
    if to_ts:
        if to_ts.tzinfo is None:
            to_ts = to_ts.replace(tzinfo=UTC)
        stmt = stmt.where(AuditEventRecord.created_at <= to_ts)
        count_stmt = count_stmt.where(AuditEventRecord.created_at <= to_ts)

    total = (await session.execute(count_stmt)).scalar_one()
    stmt = (
        stmt.order_by(AuditEventRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": str(r.id),
                "event": r.event,
                "actor": r.actor,
                "action": r.action,
                "detail": r.detail,
                "ip": r.ip,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
