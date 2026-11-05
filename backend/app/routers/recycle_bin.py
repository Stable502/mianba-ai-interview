"""回收站路由：被删除的简历与面试记录保留 7 天，可恢复或彻底删除"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import get_current_user
from app.models import InterviewReport, InterviewSession, Resume, User
from app.services.recycle_service import RETENTION_DAYS, purge_resume, purge_session

router = APIRouter(prefix="/api/recycle-bin", tags=["回收站"])


def _expires_at(deleted_at: datetime) -> datetime:
    return deleted_at + timedelta(days=RETENTION_DAYS)


def _days_left(deleted_at: datetime) -> int:
    """距离自动清除的剩余天数（不足 1 天按 1 天显示）"""
    delta = _expires_at(deleted_at) - datetime.now()
    return max(1, delta.days + (1 if delta.seconds else 0)) if delta.total_seconds() > 0 else 0


def _resume_item(r: Resume) -> dict:
    return {
        "item_type": "resume",
        "id": r.id,
        "title": r.title,
        "meta": None,
        "deleted_at": r.deleted_at,
        "expires_at": _expires_at(r.deleted_at),
        "days_left": _days_left(r.deleted_at),
    }


def _session_item(s: InterviewSession, report: InterviewReport | None) -> dict:
    return {
        "item_type": "report",
        "id": s.id,
        "title": (
            s.job_position.position_title if s.job_position else None
        ) or (s.persona.name if s.persona else "通用练习"),
        "meta": {
            "interview_type": s.interview_type,
            "overall_score": float(report.overall_score) if report and report.overall_score is not None else None,
        },
        "deleted_at": s.deleted_at,
        "expires_at": _expires_at(s.deleted_at),
        "days_left": _days_left(s.deleted_at),
    }


@router.get("")
def list_recycle_bin(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """回收站列表：软删除的简历 + 面试记录"""
    resumes = (
        db.query(Resume)
        .options(selectinload(Resume.experiences))
        .filter(Resume.user_id == current_user.id, Resume.deleted_at.isnot(None))
        .order_by(Resume.deleted_at.desc())
        .all()
    )
    sessions = (
        db.query(InterviewSession)
        .options(selectinload(InterviewSession.persona), selectinload(InterviewSession.job_position))
        .filter(InterviewSession.user_id == current_user.id, InterviewSession.deleted_at.isnot(None))
        .order_by(InterviewSession.deleted_at.desc())
        .all()
    )
    report_map = {
        r.session_id: r
        for r in db.query(InterviewReport)
        .filter(InterviewReport.user_id == current_user.id)
        .all()
    }
    return {
        "retention_days": RETENTION_DAYS,
        "resumes": [_resume_item(r) for r in resumes],
        "reports": [_session_item(s, report_map.get(s.id)) for s in sessions],
    }


@router.post("/{item_type}/{item_id}/restore")
def restore_item(
    item_type: str,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """从回收站恢复"""
    if item_type == "resume":
        resume = db.get(Resume, item_id)
        if not resume or resume.user_id != current_user.id or resume.deleted_at is None:
            raise HTTPException(status_code=404, detail="回收站中不存在该简历")
        resume.deleted_at = None
        # 恢复时若它原是默认简历，重新设为默认（删除期间默认位可能已被顶替）
        if resume.is_default == 1:
            db.query(Resume).filter(
                Resume.user_id == current_user.id,
                Resume.id != resume.id,
                Resume.deleted_at.is_(None),
            ).update({"is_default": 0})
        db.commit()
        return {"restored": True, "item_type": "resume", "id": item_id}

    if item_type == "report":
        sess = db.get(InterviewSession, item_id)
        if not sess or sess.user_id != current_user.id or sess.deleted_at is None:
            raise HTTPException(status_code=404, detail="回收站中不存在该面试记录")
        sess.deleted_at = None
        db.commit()
        return {"restored": True, "item_type": "report", "id": item_id}

    raise HTTPException(status_code=400, detail="未知的回收站类型")


@router.delete("/clear")
def clear_recycle_bin(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """清空当前用户回收站（彻底删除全部）"""
    count = 0
    resumes = db.query(Resume).filter(
        Resume.user_id == current_user.id, Resume.deleted_at.isnot(None)
    ).all()
    for r in resumes:
        purge_resume(db, r)
        count += 1
    sessions = db.query(InterviewSession).filter(
        InterviewSession.user_id == current_user.id, InterviewSession.deleted_at.isnot(None)
    ).all()
    for s in sessions:
        purge_session(db, s.id)
        count += 1
    db.commit()
    return {"purged": count}


@router.delete("/{item_type}/{item_id}")
def purge_item(
    item_type: str,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """彻底删除（不可恢复）"""
    if item_type == "resume":
        resume = db.get(Resume, item_id)
        if not resume or resume.user_id != current_user.id or resume.deleted_at is None:
            raise HTTPException(status_code=404, detail="回收站中不存在该简历")
        purge_resume(db, resume)
        db.commit()
        return {"purged": True, "item_type": "resume", "id": item_id}

    if item_type == "report":
        sess = db.get(InterviewSession, item_id)
        if not sess or sess.user_id != current_user.id or sess.deleted_at is None:
            raise HTTPException(status_code=404, detail="回收站中不存在该面试记录")
        purge_session(db, sess.id)
        db.commit()
        return {"purged": True, "item_type": "report", "id": item_id}

    raise HTTPException(status_code=400, detail="未知的回收站类型")
