"""账户与会员域模型"""
from datetime import datetime

from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Integer, SmallInteger, String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    phone = Column(String(20), nullable=True, unique=True, comment="手机号")
    email = Column(String(128), nullable=True, unique=True, comment="邮箱")
    wechat_openid = Column(String(64), nullable=True, unique=True, comment="微信 openid")
    password_hash = Column(String(255), nullable=True, comment="第三方登录可空")
    nickname = Column(String(64), nullable=False, default="", comment="昵称")
    status = Column(SmallInteger, nullable=False, default=1, comment="1正常 2封禁")
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    deleted_at = Column(DateTime, nullable=True, comment="软删")

    memberships = relationship("Membership", back_populates="user")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(32), nullable=False, unique=True, comment="free/monthly/quarterly/yearly")
    name = Column(String(64), nullable=False, comment="展示名")
    price_cents = Column(Integer, nullable=False, default=0, comment="分")
    period_days = Column(Integer, nullable=False, default=0, comment="0=免费档")
    max_interviews_month = Column(Integer, nullable=True, comment="每月面试次数上限, NULL=无限")
    full_report_enabled = Column(SmallInteger, nullable=False, default=0, comment="是否含完整诊断报告")
    pdf_export_enabled = Column(SmallInteger, nullable=False, default=0, comment="是否可导出PDF")
    persona_premium = Column(SmallInteger, nullable=False, default=0, comment="是否解锁全部面试官风格")
    is_active = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class Membership(Base):
    __tablename__ = "memberships"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    plan_id = Column(BigInteger, ForeignKey("plans.id"), nullable=False)
    status = Column(SmallInteger, nullable=False, default=1, comment="1生效 2已过期 3已退订")
    started_at = Column(DateTime, nullable=False)
    expired_at = Column(DateTime, nullable=False)
    auto_renew = Column(SmallInteger, nullable=False, default=0, comment="自动续费")
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    user = relationship("User", back_populates="memberships")
    plan = relationship("Plan")


class Order(Base):
    __tablename__ = "orders"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_no = Column(String(40), nullable=False, unique=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    plan_id = Column(BigInteger, ForeignKey("plans.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(SmallInteger, nullable=False, default=1, comment="1待支付 2已支付 3已退款 4已关闭")
    channel = Column(String(20), nullable=True, comment="wechat/alipay")
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    plan = relationship("Plan")


class UsageQuota(Base):
    __tablename__ = "usage_quotas"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    period = Column(String(7), nullable=False, comment="结算月, 如 2026-09")
    quota_limit = Column(Integer, nullable=False, comment="当月上限")
    quota_used = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
