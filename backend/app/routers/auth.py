"""认证路由：注册 / 登录 / 当前用户 / 验证码 / 游客体验"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.auth import (
    LoginRequest, RegisterRequest, SendCodeRequest, SendCodeResponse,
    TokenResponse, UserBrief,
)
from app.services.quota import get_current_plan, get_or_create_quota
from app.services.security import create_access_token, hash_password, verify_password
from app.services.verification_service import (
    is_valid_email, send_code, verify_code,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


def build_user_brief(db: Session, user: User) -> UserBrief:
    """构造用户简要信息（含计划与额度）"""
    plan = get_current_plan(db, user.id)
    quota = get_or_create_quota(db, user.id)
    is_member = plan.code != "free"
    remain = None if plan.max_interviews_month is None else max(quota.quota_limit - quota.quota_used, 0)
    nickname = user.nickname or user.phone or user.email or "用户"
    return UserBrief(
        id=user.id,
        nickname=nickname,
        phone=user.phone,
        email=user.email,
        avatar_text=nickname[0] if nickname else "用",
        plan_name=plan.name,
        plan_code=plan.code,
        quota_limit=quota.quota_limit if plan.max_interviews_month is not None else None,
        quota_used=quota.quota_used,
        quota_remain=remain,
        is_member=is_member,
    )


@router.post("/send-code", response_model=SendCodeResponse)
def send_verification_code(payload: SendCodeRequest, db: Session = Depends(get_db)):
    """发送邮箱验证码（SMTP）。演示模式下 dev_code 返回验证码明文。"""
    dev_code = send_code(db, payload.account.strip(), payload.scene)
    return SendCodeResponse(sent=True, dev_code=dev_code)


@router.post("/guest", response_model=TokenResponse)
def guest_register(db: Session = Depends(get_db)):
    """游客体验模式：直接创建临时账号（免验证码，服务端受控）"""
    rand = uuid.uuid4().hex[:10]
    user = User(
        email=f"guest_{rand}@demo.com",
        password_hash=hash_password(uuid.uuid4().hex),
        nickname="体验用户",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    from app.services.preset_data import ensure_preset_positions
    ensure_preset_positions(db, user.id)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """注册：邮箱 + 邮箱验证码 + 密码（验证码证明本人持有该邮箱）"""
    account = payload.account.strip()
    if not is_valid_email(account):
        raise HTTPException(status_code=400, detail="请使用邮箱注册")
    verify_code(db, account, payload.sms_code or "", scene="register")

    if db.query(User).filter(User.email == account).first():
        raise HTTPException(status_code=400, detail="该邮箱已注册，请直接登录")

    user = User(
        email=account,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname or account.split("@")[0],
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 为新用户播种内置预设岗位（幂等，仅当无岗位时）
    from app.services.preset_data import ensure_preset_positions
    ensure_preset_positions(db, user.id)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """登录：手机号或邮箱 + 密码"""
    account = payload.account.strip()
    is_email = "@" in account

    user = None
    if is_email:
        user = db.query(User).filter(User.email == account).first()
    else:
        user = db.query(User).filter(User.phone == account).first()

    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if user.status != 1:
        raise HTTPException(status_code=403, detail="账号已被封禁")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserBrief)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_user_brief(db, current_user)
