# 阶段 4: 授权与越权防护

**开始时间**: 2026-07-08T11:00:00+08:00
**结束时间**: 2026-07-08T11:30:00+08:00
**风险计数**: P0 × 1 / P1 × 3 / P2 × 1 / P3 × 0

---

## AUTHZ-01 [P0] Admin 21 个端点无权限控制

**CVSS 3.1**: 9.1
**文件**: `admin.py:29`, `admin_prompts.py:47`, `admin_graph_nodes.py:35`
**详情**: 任何人可审核/删节点/改配置/修改 prompt/重置数据。

**最小修复**:
```python
async def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403)
    return user

@router.get("/stats", dependencies=[Depends(require_admin)])
```

---

## AUTHZ-02 [P1] IDOR: match/learning 无属主校验

**CVSS 3.1**: 6.5
**文件**: `match.py:99-108`, `learning.py:234-285`
**详情**: 接受任意 `match_id`/`plan_id`，无属主校验。

---

## AUTHZ-03 [P1] batch 端点接受无校验 dict

**CVSS 3.1**: 6.1
**文件**: `match.py:157-159`

---

## AUTHZ-04 [P2] Judge 接受服务器文件路径

**CVSS 3.1**: 5.3
**文件**: `judge.py:56-58` (与 INJ-01 重复)

---

## AUTHZ-05 [P2] Pipeline config 无认证可修改

**CVSS 3.1**: 6.5
**文件**: `pipeline/routes.py:430-452`

---

**下一阶段输入交接**:
- Admin 无权限为 P0
- IDOR 需认证系统就位后修复
