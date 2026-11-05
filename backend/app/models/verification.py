"""邮箱验证码模型（表沿用历史 sms_codes，字段 phone 存储邮箱账号）"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database import Base


class VerificationCode(Base):
    __tablename__ = "sms_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account = Column("phone", String(255), nullable=False, index=True, comment="接收邮箱")
    code = Column(String(6), nullable=False, comment="6位验证码")
    scene = Column(String(20), nullable=False, default="register", comment="场景: register/login")
    used = Column(Boolean, nullable=False, default=False, comment="是否已使用")
    fail_count = Column(Integer, nullable=False, default=0, comment="校验失败次数")
    expires_at = Column(DateTime, nullable=False, comment="过期时间")
    created_at = Column(DateTime, default=datetime.now, comment="发送时间")
