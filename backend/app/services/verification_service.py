"""邮箱验证码业务逻辑：发送（频控/场景校验）与校验"""
import random
import re
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import VerificationCode, User
from app.services.email_client import email_client

CODE_TTL_SECONDS = 300      # 验证码有效期 5 分钟
RESEND_INTERVAL_SECONDS = 60  # 同一邮箱 60 秒内只能发一次
MAX_FAIL_COUNT = 5          # 同一验证码最多输错 5 次
EMAIL_REGEX = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email or ""))


def send_code(db: Session, email: str, scene: str) -> str | None:
    """发送邮箱验证码（SMTP）。

    返回 dev_code（演示模式未配置 SMTP 时），真实通道返回 None。
    - 注册场景：邮箱必须未注册（服务端兜底，防止对已注册邮箱发码）
    - 登录场景：邮箱必须已注册
    """
    email = (email or "").strip()
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if scene not in ("register", "login"):
        raise HTTPException(status_code=400, detail="无效的验证码场景")

    user = db.query(User).filter(User.email == email).first()
    if scene == "register" and user:
        raise HTTPException(status_code=400, detail="该邮箱已注册，请直接登录")
    if scene == "login" and not user:
        raise HTTPException(status_code=400, detail="该邮箱尚未注册，请先注册")

    # 频控：60 秒内不允许重复发送
    latest = (
        db.query(VerificationCode)
        .filter(VerificationCode.account == email, VerificationCode.scene == scene)
        .order_by(VerificationCode.id.desc())
        .first()
    )
    if latest and (datetime.now() - latest.created_at).total_seconds() < RESEND_INTERVAL_SECONDS:
        remain = RESEND_INTERVAL_SECONDS - int((datetime.now() - latest.created_at).total_seconds())
        raise HTTPException(status_code=429, detail=f"发送过于频繁，请 {remain} 秒后重试")

    code = f"{random.randint(0, 999999):06d}"
    record = VerificationCode(
        account=email,
        code=code,
        scene=scene,
        used=False,
        fail_count=0,
        expires_at=datetime.now() + timedelta(seconds=CODE_TTL_SECONDS),
    )
    db.add(record)
    db.commit()

    ok, msg = email_client.send(email, code)
    if not ok:
        raise HTTPException(status_code=502, detail=msg)

    # 演示模式：把验证码回传给前端做友好提示（配置 SMTP 后此返回为 None）
    return code if not email_client.is_configured() else None


def verify_code(db: Session, email: str, code: str, scene: str) -> bool:
    """校验验证码：成功返回 True 并标记已使用；失败抛出 400"""
    email = (email or "").strip()
    code = (code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="请输入验证码")

    record = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.account == email,
            VerificationCode.scene == scene,
            VerificationCode.used == False,  # noqa: E712
        )
        .order_by(VerificationCode.id.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=400, detail="请先获取验证码")
    if datetime.now() > record.expires_at:
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
    if record.fail_count >= MAX_FAIL_COUNT:
        raise HTTPException(status_code=400, detail="验证码错误次数过多，请重新获取")
    if record.code != code:
        record.fail_count += 1
        db.commit()
        raise HTTPException(status_code=400, detail="验证码错误，请重新输入")

    record.used = True
    db.commit()
    return True
