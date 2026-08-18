"""Import JD API endpoints (Task 4).

POST /api/v1/import/jd - CSV 上传导入
POST /api/v1/import/jd/json - JSON 直接导入
两个端点都需要 admin 权限，会写 audit log。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.dependencies import require_admin
from app.schemas.import_jd import ImportRequest, ImportResult
from app.services.csv_parser import parse_csv
from app.services.import_service import import_items

router = APIRouter(prefix="/import", tags=["import"])

@router.post("/jd", response_model=ImportResult, dependencies=[Depends(require_admin)])
async def import_jd_csv(
 request: Request,
 file: UploadFile = File(..., description="CSV 文件"),
 source_name: str = Form(..., max_length=100, description="数据源标注"),
 platform: str = Form("manual", description="manual | bosszhipin | lagou | ..."),
 session: AsyncSession = Depends(get_db_session),
) -> ImportResult:
 """CSV 上传导入。"""
 if not file.filename or not file.filename.lower.endswith(".csv"):
 raise HTTPException(400, "file must be .csv")

 content = await file.read
 if not content:
 raise HTTPException(400, "empty file")

 try:
 items_raw = parse_csv(content)
 except ValueError as e:
 raise HTTPException(400, str(e)) from e

 if not items_raw:
 raise HTTPException(400, "no valid items in CSV (need job_title + clean_text columns)")

 user = request.state.user if hasattr(request.state, "user") else {"sub": "admin"}
 result = await import_items(
 session=session,
 items=items_raw,
 source_name=source_name,
 platform=platform,
 actor=user.get("sub", "admin"),
 )
 return ImportResult(**result)

@router.post("/jd/json", response_model=ImportResult, dependencies=[Depends(require_admin)])
async def import_jd_json(
 body: ImportRequest,
 request: Request,
 session: AsyncSession = Depends(get_db_session),
) -> ImportResult:
 """JSON 直接导入。"""
 if not body.items:
 raise HTTPException(400, "items required")

 user = request.state.user if hasattr(request.state, "user") else {"sub": "admin"}
 items_dicts = [item.model_dump for item in body.items]
 result = await import_items(
 session=session,
 items=items_dicts,
 source_name=body.source_name,
 platform=body.platform,
 actor=user.get("sub", "admin"),
 )
 return ImportResult(**result)
