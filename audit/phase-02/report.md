# 阶段 2: 身份认证与会话管理

**开始时间**: 2026-07-08T10:00:00+08:00
**结束时间**: 2026-07-08T10:30:00+08:00
**风险计数**: P0 × 1 / P1 × 1 / P2 × 2 / P3 × 0

---

## AUTH-01 [P0] 全部端点无认证 — 14 个路由模块裸奔

**CVSS 3.1**: 9.8 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H)
**文件**: `backend/app/dependencies.py` (全文 32 行)
**详情**: 仅提供 `get_neo4j_driver`/`get_redis_client`/`get_db_session` 三个资源注入，无 `get_current_user`。所有 95 个端点零鉴权。

**最小修复**:
```python
# backend/app/dependencies.py
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**验证方式**: `curl -X POST http://localhost:8000/api/v1/admin/stats` 应返回 401。

---

## AUTH-02 [P1] 无登录/注册端点

**CVSS 3.1**: 7.5
**详情**: 搜索 `login`, `register`, `password`, `hash_password` 均无实现。`secret_key` 仅用于启动占位符检测。

**最小修复**: 添加 `/api/v1/auth/login` 和 `/api/v1/auth/register`，密码用 bcrypt 存储。

---

## AUTH-03 [P2] user_id 硬编码 "anonymous"

**CVSS 3.1**: 5.4
**文件**: `learning.py:132`, `learning_models.py:36-38`
**详情**: 查询硬编码 `where(user_id == "anonymous")`，任何人可读取所有学习计划。

**最小修复**: `user_id` 从认证依赖获取。

---

## AUTH-04 [P2] CORS methods/headers 过宽

**CVSS 3.1**: 4.3
**文件**: `main.py:43-49`
**详情**: `allow_credentials=True` + `allow_methods=["*"]` + `allow_headers=["*"]`。

**最小修复**: 限制为 `["GET","POST","PUT","DELETE","PATCH"]` 和 `["Content-Type","Authorization"]`。

---

**下一阶段输入交接**:
- 全部端点无认证 → 阶段 4 授权检查无法实施
- `user_id` 硬编码 → IDOR 风险高
