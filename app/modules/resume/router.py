"""简历模块路由：上传、状态查询、报告获取、PDF 导出、历史列表。"""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.modules.resume import report_export
from app.modules.resume.service import (
    create_resume_record,
    get_resume_by_id,
)
from app.modules.resume.tasks import analyze_resume_task

router = APIRouter(prefix="/resume", tags=["resume"])

UPLOAD_DIR = Path("./data/resumes")
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}


# ── 响应模型 ──────────────────────────────────────────────

class UploadResponse(BaseModel):
    resume_id: str
    status: str


class StatusResponse(BaseModel):
    resume_id: str
    filename: str
    status: str
    target_role: str
    created_at: str


class ReportResponse(BaseModel):
    resume_id: str
    filename: str
    status: str
    target_role: str
    analysis_result: dict
    created_at: str


class ResumeListItem(BaseModel):
    resume_id: str
    filename: str
    status: str
    target_role: str
    created_at: str


class ResumeListResponse(BaseModel):
    total: int
    items: list[ResumeListItem]


# ── 端点 ──────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_resume(
    file: UploadFile = File(...),
    target_role: str = Form(default=""),
    db: Session = Depends(get_db),
):
    # 校验文件格式
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式 '{ext}'，仅接受: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 保存文件到 data/resumes/
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    resume_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{resume_id}{ext}"
    filename = file.filename or file_path.name

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    if file_path.stat().st_size == 0:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="空文件无法分析")

    create_resume_record(
        db=db,
        resume_id=resume_id,
        filename=filename,
        file_path=str(file_path),
        file_ext=ext,
        target_role=target_role,
    )

    # 触发异步分析任务
    analyze_resume_task.delay(resume_id, str(file_path), target_role)

    return UploadResponse(resume_id=resume_id, status="analyzing")


# /list 在 /{resume_id} 路由之前定义，避免被路径参数捕获
@router.get("/list", response_model=ResumeListResponse)
async def list_resumes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    from app.database.models import ResumeRecord

    query = db.query(ResumeRecord).order_by(ResumeRecord.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return ResumeListResponse(
        total=total,
        items=[
            ResumeListItem(
                resume_id=str(r.resume_id),
                filename=r.filename,
                status=r.status,
                target_role=r.target_role or "",
                created_at=str(r.created_at),
            )
            for r in items
        ],
    )


@router.get("/{resume_id}/status", response_model=StatusResponse)
async def get_status(resume_id: str, db: Session = Depends(get_db)):
    record = get_resume_by_id(db, resume_id)
    if not record:
        raise HTTPException(status_code=404, detail="简历记录不存在")

    return StatusResponse(
        resume_id=str(record.resume_id),
        filename=record.filename,
        status=record.status,
        target_role=record.target_role or "",
        created_at=str(record.created_at),
    )


@router.get("/{resume_id}/report", response_model=ReportResponse)
async def get_report(resume_id: str, db: Session = Depends(get_db)):
    record = get_resume_by_id(db, resume_id)
    if not record:
        raise HTTPException(status_code=404, detail="简历记录不存在")

    if record.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"分析尚未完成，当前状态: {record.status}",
        )

    return ReportResponse(
        resume_id=str(record.resume_id),
        filename=record.filename,
        status=record.status,
        target_role=record.target_role or "",
        analysis_result=record.analysis_result or {},
        created_at=str(record.created_at),
    )


@router.get("/{resume_id}/export")
async def export_pdf(resume_id: str, db: Session = Depends(get_db)):
    record = get_resume_by_id(db, resume_id)
    if not record:
        raise HTTPException(status_code=404, detail="简历记录不存在")

    if record.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"分析尚未完成，当前状态: {record.status}",
        )

    # PDF 输出路径：data/resumes/report_{resume_id}.pdf
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = UPLOAD_DIR / f"report_{resume_id}.pdf"

    # 仅当文件不存在时生成，避免重复计算
    if not pdf_path.exists():
        report_export.export_report_pdf(record.analysis_result, str(pdf_path))

    return FileResponse(
        path=str(pdf_path),
        filename=f"report_{resume_id}.pdf",
        media_type="application/pdf",
    )
