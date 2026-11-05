"""用户与会员相关路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Plan, User
from app.routers.auth import build_user_brief
from app.schemas.auth import UserBrief
from app.schemas.report import PlanOut

router = APIRouter(prefix="/api", tags=["用户与会员"])


@router.get("/users/me", response_model=UserBrief)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_user_brief(db, current_user)


@router.get("/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    """订阅计划列表（会员中心定价）"""
    return db.query(Plan).filter(Plan.is_active == 1).order_by(Plan.price_cents.asc()).all()
