"""会员订购：订单创建 / 支付 / 订单列表

支付渠道：channel="mock" 内置模拟收银台（演示环境）；alipay 支付宝沙箱/正式环境。
"""
import random
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Membership, Order, Plan, User
from app.services.alipay_client import alipay_client
from app.services.quota import get_or_create_quota

router = APIRouter(prefix="/api/orders", tags=["会员订购"])

VALID_CODES = {"monthly", "quarterly", "yearly"}
PAID_TRADE_STATUS = {"TRADE_SUCCESS", "TRADE_FINISHED"}


class OrderCreate(BaseModel):
    plan_code: str
    channel: str = "mock"


class OrderPay(BaseModel):
    channel: str = "mock"


class OrderOut(BaseModel):
    order_no: str
    plan_code: str
    plan_name: str
    amount_cents: int
    status: int  # 1待支付 2已支付 3已退款 4已关闭
    channel: str | None = None
    paid_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def build(cls, order: Order) -> "OrderOut":
        return cls(
            order_no=order.order_no,
            plan_code=order.plan.code,
            plan_name=order.plan.name,
            amount_cents=order.amount_cents,
            status=order.status,
            channel=order.channel,
            paid_at=order.paid_at,
            created_at=order.created_at,
        )


class PayResult(BaseModel):
    order_no: str
    status: int  # 1待支付 2已支付
    plan_code: str | None = None
    plan_name: str | None = None
    expired_at: datetime | None = None
    pay_url: str | None = None      # 支付宝：收银台跳转 URL
    message: str


def _gen_order_no() -> str:
    return f"MB{time.strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"


def _activate_membership(db: Session, user_id: int, plan: Plan) -> datetime:
    """开通/续费会员：已有生效会员则在原到期日上叠加时长，否则从现在起算。返回新到期日。"""
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
        # 续费/叠加：在现有到期日基础上延长新计划的时长，并切换到新计划权益
        membership.expired_at = membership.expired_at + timedelta(days=plan.period_days)
        membership.plan_id = plan.id
        expired = membership.expired_at
    else:
        expired = now + timedelta(days=plan.period_days)
        db.add(
            Membership(
                user_id=user_id,
                plan_id=plan.id,
                status=1,
                started_at=now,
                expired_at=expired,
            )
        )
    db.commit()
    # 会员权益即时生效：刷新当月额度上限（免费 2 次 → 会员无限）
    get_or_create_quota(db, user_id)
    return expired


def _mark_paid_and_activate(db: Session, order: Order, channel: str) -> datetime:
    """订单标记已支付并开通/续费会员（支付回调与轮询查询共用）"""
    order.status = 2
    order.channel = channel
    order.paid_at = datetime.now()
    db.commit()
    plan = db.get(Plan, order.plan_id)
    return _activate_membership(db, order.user_id, plan)


@router.post("", response_model=OrderOut)
def create_order(
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建会员订购订单（待支付）"""
    if payload.plan_code not in VALID_CODES:
        raise HTTPException(status_code=400, detail="无效的套餐类型")
    plan = db.query(Plan).filter(Plan.code == payload.plan_code, Plan.is_active == 1).first()
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")
    if plan.price_cents <= 0:
        raise HTTPException(status_code=400, detail="免费套餐无需订购")

    order = Order(
        order_no=_gen_order_no(),
        user_id=current_user.id,
        plan_id=plan.id,
        amount_cents=plan.price_cents,
        status=1,
        channel=payload.channel,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return OrderOut.build(order)


@router.get("/pay-config")
def pay_config():
    """支付渠道配置：前端据此决定收银台展示哪些渠道"""
    return {
        "alipay_enabled": alipay_client.is_configured(),
    }


@router.post("/{order_no}/pay", response_model=PayResult)
def pay_order(
    order_no: str,
    payload: OrderPay,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """支付订单：mock 渠道即时到账开通；alipay 渠道返回收银台跳转 URL 等待付款

    支付宝流程：前端跳转 pay_url 付款 → 异步回调 /alipay/notify（生产）或前端轮询
    GET /{order_no}（本地开发，内部调 alipay.trade.query）完成开通。
    """
    order = db.query(Order).filter(Order.order_no == order_no, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == 2:
        raise HTTPException(status_code=400, detail="订单已支付，请勿重复支付")
    if order.status != 1:
        raise HTTPException(status_code=400, detail="订单已关闭或不可支付")
    plan = db.get(Plan, order.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")

    if payload.channel == "alipay":
        if not alipay_client.is_configured():
            raise HTTPException(status_code=400, detail="支付宝支付未配置，请在 backend/.env 填写 ALIPAY_* 配置")
        order.channel = "alipay"
        db.commit()
        pay_url = alipay_client.page_pay_url(
            out_trade_no=order.order_no,
            total_yuan=f"{order.amount_cents / 100:.2f}",
            subject=f"面霸AI-{plan.name}",
        )
        return PayResult(
            order_no=order.order_no,
            status=1,
            pay_url=pay_url,
            message="已跳转支付宝收银台，请在新窗口完成支付",
        )

    # 模拟支付成功（mock 渠道即时开通）
    expired = _mark_paid_and_activate(db, order, payload.channel or "mock")
    return PayResult(
        order_no=order.order_no,
        status=2,
        plan_code=plan.code,
        plan_name=plan.name,
        expired_at=expired,
        message=f"{plan.name} 开通成功，有效期至 {expired.strftime('%Y-%m-%d')}",
    )


@router.get("/{order_no}", response_model=PayResult)
def order_status(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询订单状态；支付宝订单待支付时主动向支付方查询（本地开发无公网回调的替代方案）"""
    order = db.query(Order).filter(Order.order_no == order_no, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    plan = db.get(Plan, order.plan_id)

    if order.status == 1 and order.channel == "alipay":
        trade_status = alipay_client.query_trade_status(order.order_no)
        if trade_status in PAID_TRADE_STATUS:
            expired = _mark_paid_and_activate(db, order, "alipay")
            return PayResult(
                order_no=order.order_no,
                status=2,
                plan_code=plan.code,
                plan_name=plan.name,
                expired_at=expired,
                message=f"{plan.name} 开通成功，有效期至 {expired.strftime('%Y-%m-%d')}",
            )

    return PayResult(
        order_no=order.order_no,
        status=order.status,
        plan_code=plan.code if plan else None,
        plan_name=plan.name if plan else None,
        message="等待支付" if order.status == 1 else "已支付",
    )


@router.post("/alipay/notify")
async def alipay_notify(request: Request, db: Session = Depends(get_db)):
    """支付宝异步回调（生产环境使用，需公网可访问）：验签 → 开通会员 → 返回 success"""
    form = await request.form()
    params = {k: v for k, v in form.items()}
    if not alipay_client.verify(params):
        return "fail"
    if params.get("trade_status") not in PAID_TRADE_STATUS:
        return "success"
    order = db.query(Order).filter(Order.order_no == params.get("out_trade_no")).first()
    if not order or order.status == 2:
        return "success"
    # 校验回调金额与订单一致，防止篡改
    if abs(float(params.get("total_amount", 0)) - order.amount_cents / 100) > 0.001:
        return "fail"
    _mark_paid_and_activate(db, order, "alipay")
    return "success"


@router.get("", response_model=list[OrderOut])
def my_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的订单（最近 20 条）"""
    orders = (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .order_by(Order.id.desc())
        .limit(20)
        .all()
    )
    return [OrderOut.build(o) for o in orders]
