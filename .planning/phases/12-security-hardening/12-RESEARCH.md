# Phase 12: Security Hardening — Research Report

## Executive Summary

StarMap's backend security infrastructure is currently at "development-usable" level. This research identifies concrete vulnerabilities across six areas (SEC-01 through SEC-06) and provides migration strategies to reach production readiness. The most critical findings are: (1) hand-rolled JWT with no standard claim validation, (2) plaintext password comparison, (3) complete absence of IDOR protection on loop results, (4) zero ForeignKey constraints across all models, and (5) unrestricted runtime mutation of the Settings singleton.

---

## SEC-01: PyJWT Replacement for Hand-Written HMAC+base64 JWT

### Current Implementation

**File:** `backend/app/api/v1/auth.py` (lines 33-51)

The current JWT implementation is entirely hand-written:

```python
def _encode_jwt(payload: dict[str, str | int | float]) -> str:
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()
    signing_input = f"{header}.{payload_b64}".encode()
    sig = hmac.new(settings.secret_key.encode(), signing_input, hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{header}.{payload_b64}.{signature}"
```

**File:** `backend/app/dependencies.py` (lines 52-88)

The decode function mirrors the encode:

```python
def _decode_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    # Verify signature
    signing_input = f"{parts[0]}.{parts[1]}".encode()
    sig = hmac.new(settings.secret_key.encode(), signing_input, hashlib.sha256).digest()
    expected_sig = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    if not hmac.compare_digest(expected_sig, parts[2]):
        raise ValueError("Invalid JWT signature")
    # Decode payload
    payload_b64 = parts[1]
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding
    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    payload = json.loads(payload_bytes)
    # Check expiration
    exp = payload.get("exp")
    if exp and exp < time.time():
        raise ValueError("JWT expired")
    return payload
```

### Vulnerabilities Identified

1. **No algorithm claim verification**: The header always says `HS256`, but the decoder never checks the `alg` field. A crafted token with `alg: "none"` would pass the 3-part format check but the signature verification would fail (hmac.compare_digest would fail). However, the hand-rolled code is fragile and could be modified to skip verification more easily than a library.

2. **No `typ` claim enforcement**: The decoder ignores the header entirely after splitting.

3. **No claim validation beyond `exp`**: No `aud`, `iss`, `nbf`, or `jti` claims are checked. This means:
   - Tokens issued for one service can be replayed against another
   - Tokens used before their `nbf` (not-before) time are accepted
   - No token revocation mechanism exists (no `jti` for denylisting)

4. **Padding handling is manual and error-prone**: The `rstrip(b"=")` on encode and manual padding restoration on decode is a common source of subtle bugs.

5. **No leeway/clock-skew tolerance**: `exp < time.time()` is a strict comparison. Any clock skew between services causes token rejection.

6. **Signature comparison uses `hmac.compare_digest`** (good — timing-safe), but the overall implementation is still hand-rolled and not audited.

### Current JWT Payload Structure

```python
payload = {
    "sub": matched["username"],   # subject = username
    "role": matched["role"],      # role claim (admin/user)
    "username": matched["username"],  # redundant with sub
    "exp": now + settings.token_expire_hours * 3600,  # expiration (float timestamp)
    "iat": now,  # issued-at (float timestamp)
}
```

Missing claims: `aud`, `iss`, `nbf`, `jti`.

### Migration Strategy: PyJWT

**Dependency to add:** `PyJWT>=2.8,<3.0` in `pyproject.toml`

**Minimal change approach:**

1. Replace `_encode_jwt()` with:
   ```python
   import jwt
   token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
   ```

2. Replace `_decode_token()` with:
   ```python
   payload = jwt.decode(
       token,
       settings.secret_key,
       algorithms=["HS256"],
       options={"require": ["exp", "iat", "sub"]},
   )
   ```

3. This is a **drop-in replacement** — PyJWT's `encode`/`decode` with HS256 produces the exact same token format (header.payload.signature with base64url encoding). **Existing tokens in the wild remain valid** because the cryptographic output is identical.

4. The only incompatibility is padding: PyJWT uses standard base64url with padding, while the hand-rolled code strips padding (`rstrip(b"=")`). However, PyJWT's decoder handles both padded and unpadded base64url, so old tokens will still decode correctly.

**Token format compatibility matrix:**

| Token Source | PyJWT decode | Hand-rolled decode |
|---|---|---|
| Hand-rolled encoded (no padding) | Yes (PyJWT handles missing padding) | Yes |
| PyJWT encoded (with padding) | Yes | Yes (manual padding restoration handles this) |

**Conclusion:** Zero-downtime migration possible. Deploy the PyJWT change, and both old and new tokens work during the transition window (up to `token_expire_hours`).

### Files to Modify

- `backend/app/api/v1/auth.py` — replace `_encode_jwt` with `jwt.encode`
- `backend/app/dependencies.py` — replace `_decode_token` with `jwt.decode`
- `backend/pyproject.toml` — add `PyJWT` dependency

---

## SEC-02: bcrypt Password Hashing

### Current Implementation

**File:** `backend/app/api/v1/auth.py` (lines 54-69)

```python
@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> dict:
    users = settings.parsed_users
    matched = None
    for u in users:
        if u["username"] == request.username and u["password"] == request.password:
            matched = u
            break
```

**File:** `backend/app/config.py` (lines 204-218)

```python
@property
def parsed_users(self) -> list[dict[str, str]]:
    if not self.auth_users:
        return []
    users: list[dict[str, str]] = []
    for entry in self.auth_users.split(","):
        parts = entry.strip().split(":")
        if len(parts) == 3:
            users.append({"username": parts[0], "password": parts[1], "role": parts[2]})
    return users
```

The `AUTH_USERS` env var format is `username:password:role,username2:password2:role2`. Passwords are stored and compared as **plaintext strings**.

### Vulnerabilities

1. **Plaintext password storage in env vars**: Anyone with access to `.env` or the process environment sees all passwords.
2. **Plaintext comparison**: Timing attacks are possible (though Python's string comparison is somewhat variable).
3. **No password policy enforcement**: Any string is accepted.
4. **Passwords appear in logs**: If `parsed_users` is ever logged or serialized, passwords leak.

### Migration Strategy: bcrypt with Dual-Format Parsing

**Dependency to add:** `bcrypt>=4.0,<5.0` in `pyproject.toml`

**Approach: Dual-format AUTH_USERS parsing**

The key challenge is that `AUTH_USERS` is an environment variable with a colon-delimited format. bcrypt hashes contain `$` characters (e.g., `$2b$12$...`), which don't conflict with the `:` delimiter.

**New AUTH_USERS format:**
```
# Plaintext (legacy, deprecated)
admin:mypassword:admin

# bcrypt hash (new, recommended)
admin:$2b$12$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy:admin
```

**Detection logic:** A password field starting with `$2b$` or `$2a$` is treated as a bcrypt hash; otherwise, it's plaintext.

**Implementation plan:**

1. Add `bcrypt` to `pyproject.toml` dependencies.

2. Modify `config.py` `parsed_users` to store passwords as-is (no change to parsing).

3. Modify `auth.py` login to use dual verification:
   ```python
   import bcrypt

   def _verify_password(plain: str, stored: str) -> bool:
       if stored.startswith(("$2b$", "$2a$")):
           return bcrypt.checkpw(plain.encode(), stored.encode())
       # Legacy plaintext comparison (to be removed in future version)
       return plain == stored
   ```

4. Add a CLI command or startup check that warns if any AUTH_USERS entries use plaintext passwords:
   ```python
   for u in settings.parsed_users:
       if not u["password"].startswith(("$2b$", "$2a$")):
           logger.warning("User '{}' has plaintext password — migrate to bcrypt hash", u["username"])
   ```

5. Add a utility script to generate bcrypt hashes from plaintext passwords for migration.

**Production enforcement:** In production mode (`app_env=production`), reject plaintext passwords at startup:
```python
if settings.app_env == "production":
    plaintext_users = [u["username"] for u in settings.parsed_users
                       if not u["password"].startswith(("$2b$", "$2a$"))]
    if plaintext_users:
        raise RuntimeError(f"Plaintext passwords not allowed in production for users: {plaintext_users}")
```

### Files to Modify

- `backend/app/api/v1/auth.py` — add `_verify_password` with bcrypt
- `backend/app/config.py` — add startup validation for plaintext passwords in production
- `backend/pyproject.toml` — add `bcrypt` dependency

---

## SEC-03: JWT Claim Hardening (aud/iss/nbf + Clock Skew)

### Current State

The JWT payload contains only: `sub`, `role`, `username`, `exp`, `iat`.

No `aud` (audience), `iss` (issuer), `nbf` (not-before), or `jti` (JWT ID) claims are present.

### Missing Claims and Their Security Impact

| Claim | Purpose | Risk Without It |
|---|---|---|
| `aud` (audience) | Identifies intended recipient | Token replay across services |
| `iss` (issuer) | Identifies token issuer | Cannot distinguish tokens from different auth servers |
| `nbf` (not-before) | Token not valid before this time | No protection against pre-issuance use |
| `jti` (JWT ID) | Unique token identifier | No token revocation/denylisting possible |
| Clock skew leeway | Tolerance for server time differences | Tokens rejected on minor clock drift |

### Migration Strategy

**With PyJWT (SEC-01), these are simple additions:**

1. **Add claims to token issuance** (`auth.py`):
   ```python
   payload = {
       "sub": matched["username"],
       "role": matched["role"],
       "username": matched["username"],
       "exp": now + settings.token_expire_hours * 3600,
       "iat": now,
       "nbf": now,                          # NEW: not valid before issuance
       "iss": "starmap-backend",            # NEW: issuer identifier
       "aud": "starmap-api",                # NEW: audience identifier
       "jti": str(uuid.uuid4()),            # NEW: unique token ID for revocation
   }
   ```

2. **Enforce claims on decode** (`dependencies.py`):
   ```python
   payload = jwt.decode(
       token,
       settings.secret_key,
       algorithms=["HS256"],
       audience="starmap-api",              # NEW: verify audience
       issuer="starmap-backend",            # NEW: verify issuer
       options={
           "require": ["exp", "iat", "sub", "nbf", "iss", "aud"],
           "leeway": 30,                    # NEW: 30-second clock skew tolerance
       },
   )
   ```

3. **Add settings for configurable values** (`config.py`):
   ```python
   jwt_issuer: str = "starmap-backend"
   jwt_audience: str = "starmap-api"
   jwt_clock_leeway: int = Field(default=30, ge=0, description="JWT clock skew tolerance (seconds)")
   ```

**Backward compatibility concern:** Old tokens (without `aud`/`iss`/`nbf`) will fail the new `require` check. This is acceptable because:
- Token lifetime is at most `token_expire_hours` (default 24h)
- Deploy the claim hardening after the token expiry window
- Or: use a two-phase deployment — Phase A adds claims to new tokens but doesn't require them on decode; Phase B (after 24h) enforces them

**Recommended approach:** Two-phase deployment for zero-downtime:
1. Phase A: Add claims to issuance, but set `options={"require": ["exp", "iat", "sub"]}` (only require existing claims). New tokens get the new claims; old tokens still work.
2. Phase B (after `token_expire_hours`): Add `"nbf"`, `"iss"`, `"aud"` to the `require` list.

### Files to Modify

- `backend/app/api/v1/auth.py` — add `nbf`, `iss`, `aud`, `jti` to payload
- `backend/app/dependencies.py` — add audience/issuer verification and leeway
- `backend/app/config.py` — add `jwt_issuer`, `jwt_audience`, `jwt_clock_leeway` settings

---

## SEC-04: loop_results IDOR Fix (user_id + Ownership Check)

### Current State

**File:** `backend/app/models/pipeline_models.py` (lines 216-261)

The `LoopResultRecord` model has **no `user_id` column**:

```python
class LoopResultRecord(Base):
    __tablename__ = "loop_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    steps_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**File:** `backend/app/api/v1/loop.py`

All three endpoints use `get_current_user` for authentication but **never check ownership**:

- `POST /loop/run` — creates a loop result with no user association
- `GET /loop/status/{run_id}` — any authenticated user can view any run_id
- `GET /loop/history` — returns ALL loop results (no user filtering)

**File:** `backend/app/core/pipeline/loop_orchestrator.py`

- `_insert_loop_run()` creates a `LoopResultRecord` with no user_id
- `get_loop_status()` queries by `run_id` with no user filter
- `get_loop_history()` returns all records with no user filter

### IDOR Vulnerability

Any authenticated user (including `role=user`) can:
1. View any other user's loop run results via `GET /loop/status/{run_id}` (if they know or guess the run_id)
2. See all users' loop history via `GET /loop/history`
3. Loop run_ids are UUIDs, making them hard to guess, but this is still a security violation (Broken Access Control / OWASP A01:2021)

### Migration Strategy

**Step 1: Add `user_id` column to `loop_results` table**

New alembic migration (009):

```python
def upgrade() -> None:
    op.add_column("loop_results",
        sa.Column("user_id", sa.String(255), nullable=True, index=True,
                  comment="User who triggered this loop run"))
    # Historical data: set user_id to 'system' for existing rows
    op.execute("UPDATE loop_results SET user_id = 'system' WHERE user_id IS NULL")
    # Now make it NOT NULL
    op.alter_column("loop_results", "user_id", nullable=False)
```

**Step 2: Update the ORM model**

```python
class LoopResultRecord(Base):
    __tablename__ = "loop_results"
    # ... existing columns ...
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, default="system",
        comment="User who triggered this loop run",
    )
```

**Step 3: Pass user_id through the loop pipeline**

Modify `loop.py` endpoints to pass the authenticated user's identity:

```python
@router.post("/run", response_model=LoopRunResponse)
async def run_loop(
    req: LoopRunRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> LoopRunResponse:
    result = await _orchestrator.run_loop(
        jd_text=req.jd_text,
        target_position=req.target_position,
        session=session,
        user_id=user["sub"],  # NEW: pass user identity
    )
```

**Step 4: Add ownership checks to status and history**

```python
@router.get("/status/{run_id}")
async def loop_status(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict:
    status = await get_loop_status(run_id, session=session, user_id=user["sub"])
    if status is None:
        raise HTTPException(status_code=404, detail=f"Loop run '{run_id}' not found")
    return status
```

In `loop_orchestrator.py`, add `user_id` filter to queries:

```python
select(LoopResultRecord).where(
    LoopResultRecord.run_id == run_id,
    LoopResultRecord.user_id == user_id,  # NEW: ownership check
)
```

**Admin exception:** Admin users (`role=admin`) should be able to view all loop results. Add a bypass:

```python
if user.get("role") != "admin":
    query = query.where(LoopResultRecord.user_id == user_id)
```

**Historical data handling:** Existing rows get `user_id='system'`. Admin users can see them; regular users cannot. This is acceptable because historical data predates the user association feature.

### Files to Modify

- `backend/app/models/pipeline_models.py` — add `user_id` column to `LoopResultRecord`
- `backend/app/api/v1/loop.py` — pass `user_id` to orchestrator, add ownership checks
- `backend/app/core/pipeline/loop_orchestrator.py` — accept `user_id` param, filter queries
- New migration: `backend/alembic/versions/009_add_loop_results_user_id.py`

---

## SEC-05: ForeignKey Constraints on All Model Relationship Fields

### Current State: Zero FK Constraints

After analyzing all model files, **no ForeignKey constraints exist anywhere in the codebase**. All relationship fields are plain UUID or String columns with indexes but no referential integrity.

### Complete Inventory of Missing FK Constraints

| Model | Field | Type | Should Reference | Risk |
|---|---|---|---|---|
| **PositionSkillRelation** | `position_id` | UUID | `position_records.id` | Dangling references if position deleted |
| **PositionSkillRelation** | `skill_id` | UUID | `skill_records.id` | Dangling references if skill deleted |
| **ExtractionEvaluationRecord** | `extraction_id` | UUID (nullable) | `jd_extraction_records.id` | Orphaned evaluations |
| **LearningProgress** | `plan_id` | UUID | `learning_plans.id` | Orphaned progress records |
| **EvolutionChangelog** | `snapshot_from_id` | UUID (nullable) | `evolution_snapshots.id` | Broken change history |
| **EvolutionChangelog** | `snapshot_to_id` | UUID (nullable) | `evolution_snapshots.id` | Broken change history |

### String-based "soft references" (no FK possible, but need documentation)

These fields reference other entities by name (String), not by UUID. ForeignKey constraints cannot be added because the referenced column is a `name` (String) not a primary key, and the relationship is intentionally loose:

| Model | Field | References | Note |
|---|---|---|---|
| LearningPlan | `user_id` | Auth system (no users table) | No FK target exists |
| LearningPlan | `position` | `position_records.name` | Soft ref by name |
| LearningProgress | `skill_name` | `skill_records.name` | Soft ref by name |
| EvolutionSnapshot | `position_name` | `position_records.name` | Soft ref by name |
| EvolutionChangelog | `position_name` | `position_records.name` | Soft ref by name |
| EvolutionChangelog | `skill_name` | `skill_records.name` | Soft ref by name |
| EvolutionPath | `source_position` | `position_records.name` | Soft ref by name |
| EvolutionPath | `target_position` | `position_records.name` | Soft ref by name |
| SkillTimeseries | `skill_name` | `skill_records.name` | Soft ref by name |
| SkillPrerequisite | `skill` | `skill_records.name` | Soft ref by name |
| SkillPrerequisite | `prerequisite` | `skill_records.name` | Soft ref by name |

These string-based references are **by design** — they allow the system to track skills/positions that may not yet exist in the master tables (e.g., newly detected skills). Adding FK here would break the "discover first, standardize later" workflow.

### Migration Strategy for FK Constraints

**Phase 1: Data cleanup before adding constraints**

Before adding FK constraints, we must ensure no dangling references exist:

```sql
-- Check for orphaned PositionSkillRelation.position_id
SELECT psr.id, psr.position_id
FROM position_skill_relations psr
LEFT JOIN position_records pr ON psr.position_id = pr.id
WHERE pr.id IS NULL;

-- Check for orphaned PositionSkillRelation.skill_id
SELECT psr.id, psr.skill_id
FROM position_skill_relations psr
LEFT JOIN skill_records sr ON psr.skill_id = sr.id
WHERE sr.id IS NULL;

-- Check for orphaned LearningProgress.plan_id
SELECT lp.id, lp.plan_id
FROM learning_progress lp
LEFT JOIN learning_plans lplan ON lp.plan_id = lplan.id
WHERE lplan.id IS NULL;

-- Check for orphaned EvolutionChangelog snapshot references
SELECT ec.id, ec.snapshot_from_id
FROM evolution_changelog ec
LEFT JOIN evolution_snapshots es ON ec.snapshot_from_id = es.id
WHERE es.id IS NULL AND ec.snapshot_from_id IS NOT NULL;
```

**Cleanup options:**
- Delete orphaned rows (recommended for non-critical data like position_skill_relations)
- Set nullable FK fields to NULL (for extraction_id, snapshot_from_id, snapshot_to_id)
- Create missing parent records (if the data is important enough to preserve)

**Phase 2: Add FK constraints in a new migration (010)**

```python
def upgrade() -> None:
    # PositionSkillRelation -> PositionRecord
    op.create_foreign_key(
        "fk_psr_position_id",
        "position_skill_relations", "position_records",
        ["position_id"], ["id"],
        ondelete="CASCADE",
    )
    # PositionSkillRelation -> SkillRecord
    op.create_foreign_key(
        "fk_psr_skill_id",
        "position_skill_relations", "skill_records",
        ["skill_id"], ["id"],
        ondelete="CASCADE",
    )
    # ExtractionEvaluationRecord -> JDExtractionRecord
    op.create_foreign_key(
        "fk_eer_extraction_id",
        "extraction_evaluation_records", "jd_extraction_records",
        ["extraction_id"], ["id"],
        ondelete="SET NULL",
    )
    # LearningProgress -> LearningPlan
    op.create_foreign_key(
        "fk_lp_plan_id",
        "learning_progress", "learning_plans",
        ["plan_id"], ["id"],
        ondelete="CASCADE",
    )
    # EvolutionChangelog -> EvolutionSnapshot (from)
    op.create_foreign_key(
        "fk_ec_snapshot_from_id",
        "evolution_changelog", "evolution_snapshots",
        ["snapshot_from_id"], ["id"],
        ondelete="SET NULL",
    )
    # EvolutionChangelog -> EvolutionSnapshot (to)
    op.create_foreign_key(
        "fk_ec_snapshot_to_id",
        "evolution_changelog", "evolution_snapshots",
        ["snapshot_to_id"], ["id"],
        ondelete="SET NULL",
    )
```

**ON DELETE strategies:**
- `CASCADE` for strong ownership (position_skill_relations, learning_progress) — deleting the parent removes children
- `SET NULL` for nullable references (extraction_id, snapshot_from_id, snapshot_to_id) — deleting the parent nullifies the reference
- No FK for string-based soft references (by design)

**Phase 3: Update ORM models with ForeignKey declarations**

```python
# In extraction_models.py
from sqlalchemy import ForeignKey

class PositionSkillRelation(Base):
    position_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("position_records.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skill_records.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

class ExtractionEvaluationRecord(Base):
    extraction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jd_extraction_records.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
```

### Files to Modify

- `backend/app/models/extraction_models.py` — add ForeignKey to `PositionSkillRelation`, `ExtractionEvaluationRecord`
- `backend/app/models/learning_models.py` — add ForeignKey to `LearningProgress.plan_id`
- `backend/app/models/evolution_models.py` — add ForeignKey to `EvolutionChangelog` snapshot fields
- New migration: `backend/alembic/versions/010_add_foreign_key_constraints.py`

---

## SEC-06: Settings Runtime Mutation Protection

### Current State

**File:** `backend/app/api/v1/pipeline/routes.py` (lines 490-512)

```python
@router.put("/config", response_model=PipelineConfigResponse, dependencies=[Depends(require_admin)])
async def update_pipeline_config(
    body: PipelineConfigUpdateRequest,
) -> PipelineConfigResponse:
    from app.config import settings
    if body.stage_timeout is not None:
        settings.pipeline_stage_timeout = body.stage_timeout
    if body.worker_concurrency is not None:
        settings.pipeline_worker_concurrency = body.worker_concurrency
    if body.crawl_concurrency is not None:
        settings.pipeline_crawl_concurrency = body.crawl_concurrency
    if body.retry_max is not None:
        settings.pipeline_retry_max = body.retry_max
    if body.retry_backoff is not None:
        settings.pipeline_retry_backoff = body.retry_backoff
    return PipelineConfigResponse(...)
```

**File:** `backend/app/config.py` (lines 221-227)

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

### Vulnerabilities

1. **Direct mutation of a Pydantic model instance**: `settings.pipeline_stage_timeout = body.stage_timeout` directly mutates the singleton. Pydantic v2 models are mutable by default. This bypasses any validation that would normally occur at construction time.

2. **No validation on mutated values**: The `PipelineConfigUpdateRequest` schema has no constraints:
   ```python
   class PipelineConfigUpdateRequest(BaseModel):
       stage_timeout: int | None = None
       worker_concurrency: int | None = None
       crawl_concurrency: int | None = None
       retry_max: int | None = None
       retry_backoff: int | None = None
   ```
   An admin could set `stage_timeout=0` (instant timeout), `worker_concurrency=1000` (resource exhaustion), or `retry_backoff=-1` (negative backoff).

3. **No persistence**: The mutation is in-memory only. On server restart, all changes are lost. This creates an inconsistent state where the running config differs from the `.env` file.

4. **No audit trail**: There's no logging of who changed what configuration value.

5. **No rate limiting**: An admin can rapidly toggle configuration values, potentially causing instability.

6. **Thread safety**: The Settings singleton is shared across all async handlers. Concurrent mutations could cause race conditions.

### Migration Strategy

**Approach A: Frozen Settings + Explicit Mutation Method (Recommended)**

1. Make Settings immutable after construction using `model_config = SettingsConfigDict(frozen=True, ...)` — but this breaks the current mutation pattern.

2. Better: Add a controlled mutation method with validation and audit logging:

```python
class Settings(BaseSettings):
    # ... existing fields ...

    # Mutable pipeline config with validation
    _mutable_config_keys: ClassVar[set[str]] = {
        "pipeline_stage_timeout", "pipeline_worker_concurrency",
        "pipeline",
        "pipeline_crawl_concurrency", "pipeline_retry_max", "pipeline_retry_backoff",
    }

    def safe_update(self, updates: dict[str, Any], actor: str) -> dict[str, tuple[Any, Any]]:
        """Update mutable config fields with validation and audit logging.

        Returns dict of {field_name: (old_value, new_value)} for changed fields.
        Raises ValueError if any value fails validation.
        """
        changes: dict[str, tuple[Any, Any]] = {}
        for key, value in updates.items():
            if key not in self._mutable_config_keys:
                raise ValueError(f"Field '{key}' is not runtime-mutable")
            if value is None:
                continue
            # Validate using the field's own validators
            field_info = self.model_fields[key]
            # ... apply field-level validation ...
            old_value = getattr(self, key)
            object.__setattr__(self, key, value)
            changes[key] = (old_value, value)

        if changes:
            from app.utils.audit import AuditEntry, AuditEvent, audit_log
            audit_log(AuditEntry(
                event=AuditEvent.SENSITIVE_WRITE,
                actor=actor,
                action="update_pipeline_config",
                detail=f"Changed: {changes}",
                ip="",
            ))
        return changes
```

3. Add validation constraints to `PipelineConfigUpdateRequest`:

```python
class PipelineConfigUpdateRequest(BaseModel):
    stage_timeout: int | None = Field(None, ge=60, le=7200, description="Stage timeout (60-7200 seconds)")
    worker_concurrency: int | None = Field(None, ge=1, le=10, description="Worker concurrency (1-10)")
    crawl_concurrency: int | None = Field(None, ge=1, le=20, description="Crawl concurrency (1-20)")
    retry_max: int | None = Field(None, ge=0, le=10, description="Max retries (0-10)")
    retry_backoff: int | None = Field(None, ge=1, le=300, description="Retry backoff base (1-300 seconds)")
```

4. Update the endpoint to use `safe_update`:

```python
@router.put("/config", response_model=PipelineConfigResponse, dependencies=[Depends(require_admin)])
async def update_pipeline_config(
    body: PipelineConfigUpdateRequest,
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> PipelineConfigResponse:
    from app.config import settings
    updates = body.model_dump(exclude_none=True)
    settings.safe_update(updates, actor=user.get("sub", "unknown"))
    return PipelineConfigResponse(
        stage_timeout=settings.pipeline_stage_timeout,
        worker_concurrency=settings.pipeline_worker_concurrency,
        crawl_concurrency=settings.pipeline_crawl_concurrency,
        retry_max=settings.pipeline_retry_max,
        retry_backoff=settings.pipeline_retry_backoff,
    )
```

**Approach B: Database-backed config (Future consideration)**

For full production readiness, pipeline config should be persisted in the `system_config` table (which already exists). This would:
- Survive server restarts
- Support config versioning/rollback
- Enable multi-instance consistency

This is a larger change and can be deferred to a later phase. The in-memory approach with validation and audit logging is sufficient for SEC-06.

### Files to Modify

- `backend/app/config.py` — add `safe_update` method with validation and audit
- `backend/app/api/v1/pipeline/schemas.py` — add Field constraints to `PipelineConfigUpdateRequest`
- `backend/app/api/v1/pipeline/routes.py` — use `safe_update` instead of direct mutation

---

## Dependency Changes Summary

Add to `backend/pyproject.toml` `[project.dependencies]`:

```toml
"PyJWT (>=2.8,<3.0)",       # SEC-01: JWT library replacing hand-rolled implementation
"bcrypt (>=4.0,<5.0)",      # SEC-02: Password hashing
```

No other new dependencies needed.

---

## Migration Sequence

The recommended order of implementation, considering dependencies between changes:

| Step | SEC Item | Migration | Notes |
|---|---|---|---|
| 1 | SEC-01 | None (code change only) | PyJWT drop-in replacement, zero downtime |
| 2 | SEC-02 | None (code change only) | Dual-format password parsing, backward compatible |
| 3 | SEC-03 | None (code change only) | Two-phase claim hardening (add first, enforce later) |
| 4 | SEC-04 | 009_add_loop_results_user_id.py | Add user_id column, backfill with 'system' |
| 5 | SEC-05 | 010_add_foreign_key_constraints.py | Data cleanup first, then add FK constraints |
| 6 | SEC-06 | None (code change only) | Settings mutation protection |

Steps 1-3 can be deployed together as they are all code-only changes with no schema impact.
Step 4 requires a migration and should be deployed separately.
Step 5 requires data cleanup and a migration — deploy with caution and verify cleanup first.
Step 6 is independent and can be deployed at any point.

---

## Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Existing tokens break after PyJWT migration | Low | PyJWT HS256 output is format-compatible; test with old tokens |
| Plaintext passwords in production | Critical | Add startup validation to reject plaintext in production mode |
| Clock skew causes token rejection | Medium | Add 30-second leeway to JWT decode |
| IDOR on loop results | High | Add user_id + ownership checks; admin bypass for visibility |
| Dangling FK references block migration | Medium | Run data cleanup queries before adding constraints |
| Settings mutation causes instability | Medium | Add value range validation and audit logging |
| Concurrent settings mutation race condition | Low | Python GIL + async single-threaded event loop mitigates this |

---

## Key File Reference

| File | Role | SEC Items |
|---|---|---|
| `backend/app/api/v1/auth.py` | JWT issuance, login | SEC-01, SEC-02, SEC-03 |
| `backend/app/dependencies.py` | JWT decode, auth dependencies | SEC-01, SEC-03 |
| `backend/app/config.py` | Settings singleton, AUTH_USERS parsing | SEC-02, SEC-06 |
| `backend/app/models/pipeline_models.py` | LoopResultRecord model | SEC-04 |
| `backend/app/models/extraction_models.py` | PositionSkillRelation, ExtractionEvaluationRecord | SEC-05 |
| `backend/app/models/learning_models.py` | LearningProgress | SEC-05 |
| `backend/app/models/evolution_models.py` | EvolutionChangelog | SEC-05 |
| `backend/app/api/v1/loop.py` | Loop endpoints | SEC-04 |
| `backend/app/core/pipeline/loop_orchestrator.py` | Loop persistence logic | SEC-04 |
| `backend/app/api/v1/pipeline/routes.py` | Pipeline config mutation | SEC-06 |
| `backend/app/api/v1/pipeline/schemas.py` | PipelineConfigUpdateRequest | SEC-06 |
| `backend/pyproject.toml` | Dependencies | SEC-01, SEC-02 |
