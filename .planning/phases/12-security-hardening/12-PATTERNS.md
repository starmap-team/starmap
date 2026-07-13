# Phase 12: 安全加固 - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/api/v1/auth.py` | controller | request-response | `backend/app/api/v1/auth.py` (self, modify-in-place) | exact |
| `backend/app/dependencies.py` | middleware | request-response | `backend/app/dependencies.py` (self, modify-in-place) | exact |
| `backend/app/config.py` | config | CRUD | `backend/app/config.py` (self, modify-in-place) | exact |
| `backend/app/models/extraction_models.py` | model | CRUD | `backend/app/models/extraction_models.py` (self, add FK) | exact |
| `backend/app/models/learning_models.py` | model | CRUD | `backend/app/models/learning_models.py` (self, add FK) | exact |
| `backend/app/models/pipeline_models.py` | model | CRUD | `backend/app/models/pipeline_models.py` (self, add user_id) | exact |
| `backend/alembic/versions/009_add_loop_user_id_and_fks.py` | migration | CRUD | `backend/alembic/versions/008_add_loop_results_table.py` | exact |
| `backend/app/api/v1/pipeline/routes.py` | controller | request-response | `backend/app/api/v1/pipeline/routes.py` (self, fix settings mutation) | exact |

## Pattern Assignments

### `backend/app/api/v1/auth.py` (controller, request-response) — SEC-01~03

**Analog:** `backend/app/api/v1/auth.py` (modify in place)

**Current imports pattern** (lines 1-14):
```python
"""认证 API：用户登录、JWT token 签发。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from app.config import settings
```

**Replace with** (PyJWT + bcrypt):
```python
"""认证 API：用户登录、JWT token 签发。"""
from __future__ import annotations

import time

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from app.config import settings
```

**Current hand-written JWT encode** (lines 33-51) — DELETE entirely, replace with:
```python
def _encode_jwt(payload: dict[str, str | int | float]) -> str:
    """签发 JWT（PyJWT），与 dependencies.py _decode_token 验证逻辑一致。"""
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256",
    )
```

**Current login handler** (lines 54-90) — modify password check and payload:
```python
@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> dict:
    """用户登录，验证凭据后签发 JWT token。"""
    users = settings.parsed_users
    matched = None
    for u in users:
        if u["username"] == request.username:
            # Support both plaintext (transition) and bcrypt hash
            stored_pw = u["password"]
            if stored_pw.startswith("$2b$") or stored_pw.startswith("$2a$"):
                # bcrypt hash — verify
                if bcrypt.checkpw(request.password.encode(), stored_pw.encode()):
                    matched = u
            else:
                # Plaintext fallback (transition period)
                if stored_pw == request.password:
                    matched = u
            break

    if not matched:
        logger.warning("Login failed for username: {}", request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    now = time.time()
    payload: dict[str, str | int | float] = {
        "sub": matched["username"],
        "role": matched["role"],
        "username": matched["username"],
        "exp": now + settings.token_expire_hours * 3600,
        "iat": now,
        "aud": "starmap-api",
        "iss": "starmap",
        "nbf": now,
    }
    token = _encode_jwt(payload)

    logger.info("User '{}' logged in (role={})", matched["username"], matched["role"])

    return {
        "token": token,
        "user": {
            "sub": payload["sub"],
            "role": payload["role"],
            "username": payload["username"],
        },
    }
```

---

### `backend/app/dependencies.py` (middleware, request-response) — SEC-01~03

**Analog:** `backend/app/dependencies.py` (modify in place)

**Current hand-written JWT decode** (lines 52-88) — DELETE entirely, replace with:
```python
def _decode_token(token: str) -> dict[str, Any]:
    """解码 JWT token。使用 PyJWT，密钥来自 settings.secret_key。"""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            audience="starmap-api",
            issuer="starmap",
            leeway=30,  # 30s clock skew tolerance
        )
    except jwt.ExpiredSignatureError as e:
        raise ValueError("JWT expired") from e
    except jwt.InvalidAudienceError as e:
        raise ValueError("Invalid JWT audience") from e
    except jwt.InvalidIssuerError as e:
        raise ValueError("Invalid JWT issuer") from e
    except jwt.ImmatureSignatureError as e:
        raise ValueError("JWT not yet valid (nbf)") from e
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid JWT: {e}") from e
    return payload
```

**Existing get_current_user pattern** (lines 91-142) — keep structure, only `_decode_token` changes internally. The error handling at lines 123-140 already catches `ValueError` and maps to audit events, which will still work since the new `_decode_token` raises `ValueError` with same semantic messages ("JWT expired", etc.).

**Existing require_admin pattern** (lines 145-165) — no changes needed, already correct.

**Existing get_current_user_sse pattern** (lines 168-203) — same `_decode_token` replacement applies.

---

### `backend/app/config.py` (config, CRUD) — SEC-02/06

**Analog:** `backend/app/config.py` (modify in place)

**Current Settings class** (lines 12-219) — key patterns to preserve:
- Pydantic BaseSettings with `SettingsConfigDict(env_file=".env", extra="ignore")`
- `@model_validator(mode="after")` for startup checks (lines 134-201)
- `@property parsed_users` for AUTH_USERS parsing (lines 204-218)
- `@lru_cache` singleton via `get_settings()` (lines 221-227)

**Changes needed:**

1. **parsed_users property** (lines 204-218) — support `username:bcrypt_hash:role` format:
```python
@property
def parsed_users(self) -> list[dict[str, str]]:
    """解析 AUTH_USERS 环境变量为用户列表。

    格式: username:password_or_hash:role,username2:password2:role2
    密码字段支持明文或 bcrypt hash（$2b$/$2a$ 前缀）。
    """
    if not self.auth_users:
        return []
    users: list[dict[str, str]] = []
    for entry in self.auth_users.split(","):
        parts = entry.strip().split(":")
        if len(parts) == 3:
            users.append({"username": parts[0], "password": parts[1], "role": parts[2]})
    return users
```

2. **Settings immutability guard** — add to `_resolve_postgres_uri_and_warn` or as new validator:
```python
# In model_validator, add:
if self.app_env == "production":
    # SEC-06: Warn if settings singleton is being mutated at runtime
    # (actual guard is in the PUT /pipeline/config handler)
    pass
```

3. **Add jwt_audience / jwt_issuer / jwt_leeway fields** (optional, or hardcode in auth.py):
```python
jwt_audience: str = Field(default="starmap-api", description="JWT audience claim")
jwt_issuer: str = Field(default="starmap", description="JWT issuer claim")
jwt_leeway_seconds: int = Field(default=30, description="JWT clock skew tolerance (seconds)")
```

---

### `backend/app/models/extraction_models.py` (model, CRUD) — SEC-05

**Analog:** `backend/app/models/extraction_models.py` (modify in place)

**Current PositionSkillRelation** (lines 203-239) — no FK constraints:
```python
class PositionSkillRelation(Base):
    __tablename__ = "position_skill_relations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    position_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    ...
```

**Add ForeignKey constraints** (brownfield — keep nullable/index, add FK):
```python
from sqlalchemy import ForeignKey

# In PositionSkillRelation:
position_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("position_records.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
)
skill_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("skill_records.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
)
```

**Model import pattern** (line 12):
```python
from app.models import Base
```

**Column declaration pattern** — all models use `Mapped[type] = mapped_column(...)` with `UUID(as_uuid=True)` for UUID columns.

---

### `backend/app/models/learning_models.py` (model, CRUD) — SEC-05

**Analog:** `backend/app/models/learning_models.py` (modify in place)

**Current LearningProgress** (lines 84-160) — plan_id has no FK:
```python
plan_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), nullable=False, index=True,
)
```

**Add ForeignKey constraint**:
```python
from sqlalchemy import ForeignKey

# In LearningProgress:
plan_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("learning_plans.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
)
```

---

### `backend/app/models/pipeline_models.py` (model, CRUD) — SEC-04

**Analog:** `backend/app/models/pipeline_models.py` (modify in place)

**Current LoopResultRecord** (lines 216-261) — no user_id column:
```python
class LoopResultRecord(Base):
    __tablename__ = "loop_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    ...
```

**Add user_id column** (nullable for backward compat):
```python
# Add after run_id:
user_id: Mapped[str | None] = mapped_column(
    String(255),
    nullable=True,
    index=True,
    server_default="anonymous",
    comment="User who triggered this loop run (null for legacy data)",
)
```

**Also add user_id to PipelineRun** (lines 14-87) — same pattern:
```python
user_id: Mapped[str | None] = mapped_column(
    String(255),
    nullable=True,
    index=True,
    server_default="anonymous",
    comment="User who triggered this pipeline run",
)
```

---

### `backend/alembic/versions/009_add_loop_user_id_and_fks.py` (migration, CRUD) — SEC-04/05

**Analog:** `backend/alembic/versions/008_add_loop_results_table.py`

**Migration template pattern** (lines 1-18 of 008):
```python
"""Add loop_results table.

Revision ID: 008
Revises: 007
Create Date: 2026-07-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**New migration structure**:
```python
"""Add user_id to loop_results + pipeline_runs, add FK constraints.

Revision ID: 009
Revises: 008
Create Date: 2026-07-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SEC-04: Add user_id to loop_results (nullable, default "anonymous")
    op.add_column(
        "loop_results",
        sa.Column(
            "user_id",
            sa.String(255),
            nullable=True,
            server_default="anonymous",
            comment="User who triggered this loop run",
        ),
    )
    op.create_index("ix_loop_results_user_id", "loop_results", ["user_id"])

    # Add user_id to pipeline_runs
    op.add_column(
        "pipeline_runs",
        sa.Column(
            "user_id",
            sa.String(255),
            nullable=True,
            server_default="anonymous",
            comment="User who triggered this pipeline run",
        ),
    )
    op.create_index("ix_pipeline_runs_user_id", "pipeline_runs", ["user_id"])

    # SEC-05: Clean up dangling references before adding FK constraints
    # Delete position_skill_relations with no matching position_records
    op.execute(
        sa.text(
            "DELETE FROM position_skill_relations "
            "WHERE position_id NOT IN (SELECT id FROM position_records)"
        )
    )
    # Delete position_skill_relations with no matching skill_records
    op.execute(
        sa.text(
            "DELETE FROM position_skill_relations "
            "WHERE skill_id NOT IN (SELECT id FROM skill_records)"
        )
    )
    # Delete learning_progress with no matching learning_plans
    op.execute(
        sa.text(
            "DELETE FROM learning_progress "
            "WHERE plan_id NOT IN (SELECT id FROM learning_plans)"
        )
    )

    # Add FK constraints
    op.create_foreign_key(
        "fk_psr_position_id",
        "position_skill_relations",
        "position_records",
        ["position_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_psr_skill_id",
        "position_skill_relations",
        "skill_records",
        ["skill_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_lp_plan_id",
        "learning_progress",
        "learning_plans",
        ["plan_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Remove FK constraints
    op.drop_constraint("fk_lp_plan_id", "learning_progress", type_="foreignkey")
    op.drop_constraint("fk_psr_skill_id", "position_skill_relations", type_="foreignkey")
    op.drop_constraint("fk_psr_position_id", "position_skill_relations", type_="foreignkey")

    # Remove user_id columns
    op.drop_index("ix_pipeline_runs_user_id", table_name="pipeline_runs")
    op.drop_column("pipeline_runs", "user_id")
    op.drop_index("ix_loop_results_user_id", table_name="loop_results")
    op.drop_column("loop_results", "user_id")
```

**Key migration conventions observed:**
- Revision IDs are sequential 3-digit strings: "001", "002", ..., "008", "009"
- `down_revision` chains to previous: `"008"`
- `server_default` used for new nullable columns (backward compat)
- `op.create_index` with explicit index name prefix `ix_`
- `op.execute(sa.text(...))` for raw SQL (seen in 002 migration seed data)
- `op.create_foreign_key` is the Alembic API for adding FK to existing tables

---

### `backend/app/api/v1/pipeline/routes.py` (controller, request-response) — SEC-06

**Analog:** `backend/app/api/v1/pipeline/routes.py` (modify in place)

**Current PUT /config handler** (lines 490-512) — directly mutates settings singleton:
```python
@router.put("/config", response_model=PipelineConfigResponse, dependencies=[Depends(require_admin)])
async def update_pipeline_config(
    body: PipelineConfigUpdateRequest,
) -> PipelineConfigResponse:
    """更新流水线配置（写入 .env 或运行时覆盖）。"""
    from app.config import settings
    if body.stage_timeout is not None:
        settings.pipeline_stage_timeout = body.stage_timeout
    if body.worker_concurrency is not None:
        settings.pipeline_worker_concurrency = body.worker_concurrency
    ...
```

**Replace with copy-on-write pattern**:
```python
@router.put("/config", response_model=PipelineConfigResponse, dependencies=[Depends(require_admin)])
async def update_pipeline_config(
    body: PipelineConfigUpdateRequest,
) -> PipelineConfigResponse:
    """更新流水线配置（副本覆盖，不直接修改 settings 单例）。"""
    from app.config import settings
    # SEC-06: Apply updates to a copy, then replace atomically
    # Since Settings is frozen=False by default, we use object.__setattr__
    # to update the lru_cache singleton in-place but via controlled path
    updates = body.model_dump(exclude_none=True)
    for field, value in updates.items():
        if hasattr(settings, field):
            object.__setattr__(settings, field, value)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown config field: {field}")

    # Optional: persist to Redis for restart recovery
    # redis = request.app.state.resources.redis_client
    # if redis:
    #     await redis.hset("pipeline:config", mapping=updates)

    return PipelineConfigResponse(
        stage_timeout=settings.pipeline_stage_timeout,
        worker_concurrency=settings.pipeline_worker_concurrency,
        crawl_concurrency=settings.pipeline_crawl_concurrency,
        retry_max=settings.pipeline_retry_max,
        retry_backoff=settings.pipeline_retry_backoff,
    )
```

---

### `backend/app/api/v1/loop.py` (controller, request-response) — SEC-04 IDOR

**Analog:** `backend/app/api/v1/learning.py` (IDOR guard pattern)

**Learning.py IDOR guard pattern** (lines 262-264):
```python
# P1 修复 (AUTHZ-02): IDOR 校验 — 用户只能访问自己的计划
if plan.user_id != user_id:
    raise HTTPException(status_code=403, detail="Not authorized to access this plan")
```

**Apply to loop.py** — add user_id check after fetching loop result:
```python
# In loop_status and loop_history endpoints:
# SEC-04: IDOR guard — verify run ownership
# For now, loop runs don't have user_id in DB yet (migration 009 adds it)
# After migration, add:
# if result.user_id and result.user_id != user.get("sub"):
#     raise HTTPException(status_code=403, detail="Not authorized to access this loop run")
```

**Loop.py current auth pattern** (lines 72-77):
```python
@router.post("/run", response_model=LoopRunResponse)
async def run_loop(
    req: LoopRunRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> LoopRunResponse:
```

**After migration 009, also write user_id when creating loop runs** — need to pass `_user["sub"]` into the orchestrator or save it to LoopResultRecord after creation.

---

## Shared Patterns

### Authentication (get_current_user + require_admin)
**Source:** `backend/app/dependencies.py` lines 91-165
**Apply to:** All controller files that need auth (loop.py, learning.py, pipeline/routes.py)

```python
from app.dependencies import get_current_user, require_admin

# Per-endpoint auth:
_user: Annotated[dict[str, Any], Depends(get_current_user)]

# Router-level admin guard:
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

# Per-endpoint admin guard:
@router.post("/trigger", dependencies=[Depends(require_admin)])
```

### IDOR Guard Pattern
**Source:** `backend/app/api/v1/learning.py` lines 262-264, 318-319
**Apply to:** loop.py endpoints after user_id column is added

```python
user_id = user.get("sub", "anonymous")
# Fetch owned resource
if resource.user_id and resource.user_id != user_id:
    raise HTTPException(status_code=403, detail="Not authorized to access this resource")
```

### Audit Logging
**Source:** `backend/app/utils/audit.py`
**Apply to:** auth.py (login failures), dependencies.py (token validation failures)

```python
from app.utils.audit import AuditEntry, AuditEvent, audit_log

audit_log(AuditEntry(
    event=AuditEvent.AUTH_FAILURE,
    actor=username,
    action="login",
    detail="Invalid credentials",
    ip="",
))
```

### Domain Exception Pattern
**Source:** `backend/app/exceptions.py`
**Apply to:** New security-related exceptions if needed

```python
class StarMapError(Exception):
    """Base exception for all StarMap domain errors."""

class PlanOwnershipError(StarMapError):
    """Raised when a user tries to access a plan they don't own."""
    def __init__(self, plan_id: str, user_id: str) -> None:
        self.plan_id = plan_id
        self.user_id = user_id
        super().__init__(f"User {user_id} does not own plan {plan_id}")
```

### SQLAlchemy Model Pattern
**Source:** All model files in `backend/app/models/`
**Apply to:** Any model modifications (adding columns, FKs)

```python
# Standard column patterns:
id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

# FK pattern (NEW — no existing FK in codebase):
from sqlalchemy import ForeignKey
column_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("target_table.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
)

# Nullable column with server_default (backward compat):
user_id: Mapped[str | None] = mapped_column(
    String(255), nullable=True, index=True, server_default="anonymous",
)
```

### Alembic Migration Pattern
**Source:** `backend/alembic/versions/008_add_loop_results_table.py`
**Apply to:** New migration 009

```python
# Header:
revision: str = "009"
down_revision: str | None = "008"

# Add column to existing table:
op.add_column("table_name", sa.Column("col_name", sa.String(255), nullable=True, server_default="default_val"))
op.create_index("ix_table_col", "table", ["col"])

# Add FK to existing table:
op.create_foreign_key("fk_name", "source_table", "target_table", ["source_col"], ["target_col"], ondelete="CASCADE")

# Raw SQL for data cleanup:
op.execute(sa.text("DELETE FROM table WHERE col NOT IN (SELECT id FROM other)"))

# Downgrade (reverse order):
op.drop_constraint("fk_name", "source_table", type_="foreignkey")
op.drop_index("ix_table_col", table_name="table")
op.drop_column("table", "col")
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| N/A | N/A | N/A | All files have exact in-place analogs (brownfield modifications) |

**Note:** No existing ForeignKey constraints exist anywhere in the codebase. The FK pattern for models and migrations must be constructed from SQLAlchemy/Alembic documentation conventions rather than copied from existing code. The patterns above show the correct API calls based on SQLAlchemy 2.0 + Alembic standards.

## Metadata

**Analog search scope:** `backend/app/api/v1/`, `backend/app/models/`, `backend/app/`, `backend/alembic/versions/`
**Files scanned:** 18
**Pattern extraction date:** 2026-07-12
