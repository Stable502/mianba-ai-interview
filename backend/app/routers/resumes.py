"""简历管理路由"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import get_current_user
from app.models import Resume, ResumeExperience, User
from app.schemas.resume import ResumeCreate, ResumeExperienceIn, ResumeOut, ResumeUpdate

router = APIRouter(prefix="/api/resumes", tags=["简历"])


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _sync_experiences(db: Session, resume: Resume, experiences: list[ResumeExperienceIn] | None):
    if experiences is None:
        return
    # 简单实现：整体重建（删除旧的，插入新的）
    for old in list(resume.experiences):
        db.delete(old)
    db.flush()
    for i, exp in enumerate(experiences):
        db.add(ResumeExperience(
            resume_id=resume.id,
            exp_type=exp.exp_type,
            company=exp.company,
            title=exp.title,
            start_date=_parse_date(exp.start_date),
            end_date=_parse_date(exp.end_date),
            tech_stack=exp.tech_stack,
            description=exp.description,
            highlights=exp.highlights,
            sort_order=exp.sort_order if exp.sort_order else i,
        ))


@router.get("", response_model=list[ResumeOut])
def list_resumes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Resume)
        .options(selectinload(Resume.experiences))
        .filter(Resume.user_id == current_user.id, Resume.deleted_at.is_(None))
        .order_by(Resume.is_default.desc(), Resume.created_at.desc())
        .all()
    )


@router.post("", response_model=ResumeOut)
def create_resume(
    payload: ResumeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = db.query(Resume).filter(
        Resume.user_id == current_user.id, Resume.deleted_at.is_(None)
    ).count()
    resume = Resume(
        user_id=current_user.id,
        title=payload.title,
        raw_text=payload.raw_text,
        file_url=payload.file_url,
        is_default=1 if count == 0 else 0,
    )
    db.add(resume)
    db.flush()
    _sync_experiences(db, resume, payload.experiences)
    db.commit()
    db.refresh(resume)
    return _load_resume(db, resume.id)


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = _load_resume(db, resume_id)
    if not resume or resume.user_id != current_user.id or resume.deleted_at is not None:
        raise HTTPException(status_code=404, detail="简历不存在")
    return resume


@router.put("/{resume_id}", response_model=ResumeOut)
def update_resume(
    resume_id: int,
    payload: ResumeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id or resume.deleted_at is not None:
        raise HTTPException(status_code=404, detail="简历不存在")

    if payload.title is not None:
        resume.title = payload.title
    if payload.raw_text is not None:
        resume.raw_text = payload.raw_text
    if payload.is_default is not None and payload.is_default == 1:
        db.query(Resume).filter(Resume.user_id == current_user.id).update({"is_default": 0})
        resume.is_default = 1
    if payload.experiences is not None:
        _sync_experiences(db, resume, payload.experiences)
    db.commit()
    return _load_resume(db, resume_id)


@router.post("/{resume_id}/default", response_model=ResumeOut)
def set_default(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id or resume.deleted_at is not None:
        raise HTTPException(status_code=404, detail="简历不存在")
    db.query(Resume).filter(Resume.user_id == current_user.id).update({"is_default": 0})
    resume.is_default = 1
    db.commit()
    return _load_resume(db, resume_id)


@router.delete("/{resume_id}")
def delete_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除简历：移入回收站（软删除，7天后自动清理，可恢复）"""
    from datetime import datetime

    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id or resume.deleted_at is not None:
        raise HTTPException(status_code=404, detail="简历不存在")
    was_default = resume.is_default
    resume.deleted_at = datetime.now()
    resume.is_default = 0
    db.commit()
    # 若移入回收站的是默认简历，将最新的一份在用简历设为默认
    if was_default:
        latest = (
            db.query(Resume)
            .filter(Resume.user_id == current_user.id, Resume.deleted_at.is_(None))
            .order_by(Resume.created_at.desc())
            .first()
        )
        if latest:
            latest.is_default = 1
            db.commit()
    return {"ok": True}


def _load_resume(db: Session, resume_id: int) -> Resume:
    return (
        db.query(Resume)
        .options(selectinload(Resume.experiences))
        .filter(Resume.id == resume_id)
        .first()
    )
