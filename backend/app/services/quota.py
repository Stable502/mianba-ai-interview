"""会员与额度服务"""
from datetime import datetime, timedelta

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models import Membership, Plan, UsageQuota


def get_current_plan(db: Session, user_id: int) -> Plan:
    """返回用户当前生效的计划；无有效会员则返回免费档"""
    now = datetime.now()
    membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.status == 1,
            Membership.expired_at > now,
        )
        .order_by(Membership.expired_at.desc())
        .first()
    )
    if membership:
        plan = db.get(Plan, membership.plan_id)
        if plan:
            return plan
    free = db.query(Plan).filter(Plan.code == "free").first()
    return free


def is_member(db: Session, user_id: int) -> bool:
    plan = get_current_plan(db, user_id)
    return plan.code != "free"


def get_or_create_quota(db: Session, user_id: int, period: str | None = None) -> UsageQuota:
    """获取（或创建）用户当月的额度记录，并将上限与当前套餐同步（会员开通/过期即时生效）"""
    period = period or datetime.now().strftime("%Y-%m")
    plan = get_current_plan(db, user_id)
    # 免费档按计划上限；会员档 max_interviews_month 为 NULL 时表示无限
    limit = plan.max_interviews_month if plan.max_interviews_month is not None else 9999
    quota = (
        db.query(UsageQuota)
        .filter(UsageQuota.user_id == user_id, UsageQuota.period == period)
        .first()
    )
    if quota is None:
        quota = UsageQuota(user_id=user_id, period=period, quota_limit=limit, quota_used=0)
        db.add(quota)
        db.commit()
        db.refresh(quota)
    elif quota.quota_limit != limit:
        # 套餐变更（开通会员/会员过期）后同步当月额度上限
        quota.quota_limit = limit
        db.commit()
    return quota


def can_interview(db: Session, user_id: int) -> bool:
    quota = get_or_create_quota(db, user_id)
    return quota.quota_used < quota.quota_limit


def consume_quota(db: Session, user_id: int) -> bool:
    """扣减一次面试额度；成功返回 True"""
    quota = get_or_create_quota(db, user_id)
    if quota.quota_used >= quota.quota_limit:
        return False
    quota.quota_used += 1
    db.commit()
    return True
