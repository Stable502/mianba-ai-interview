"""目标岗位 JD 与面试官人设路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import InterviewerPersona, JobPosition, User
from app.schemas.resume import PersonaOut, PositionCreate, PositionOut
from app.services.quota import is_member

router = APIRouter(prefix="/api", tags=["岗位与人设"])


@router.get("/positions", response_model=list[PositionOut])
def list_positions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(JobPosition)
        .filter(JobPosition.user_id == current_user.id)
        .order_by(JobPosition.created_at.desc())
        .all()
    )


@router.post("/positions", response_model=PositionOut)
def create_position(
    payload: PositionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pos = JobPosition(user_id=current_user.id, **payload.model_dump())
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return pos


@router.delete("/positions/{position_id}")
def delete_position(
    position_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pos = db.get(JobPosition, position_id)
    if not pos or pos.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="岗位不存在")
    db.delete(pos)
    db.commit()
    return {"ok": True}


@router.get("/personas", response_model=list[PersonaOut])
def list_personas(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """面试官人设列表；会员解锁 premium 风格"""
    personas = (
        db.query(InterviewerPersona)
        .filter(InterviewerPersona.is_active == 1)
        .order_by(InterviewerPersona.id.asc())
        .all()
    )
    member = is_member(db, current_user.id)
    result = []
    for p in personas:
        p_out = PersonaOut.model_validate(p)
        # 非会员看不到 premium 风格（前端也会据此禁用）
        result.append(p_out)
    return result
