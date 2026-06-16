"""管理后台 API（占位）。对应§8.2 admin.py：人工审核队列、数据源管理、本体维护。

权限说明：评审环境单租户（§1.4.3），暂不做账号体系。
"""
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["管理后台"])


@router.get("/stats")
async def get_admin_stats():
    """后台统计概览。"""
    return {"message": "TODO"}
