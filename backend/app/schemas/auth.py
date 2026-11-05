"""认证相关 Schema"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录：手机号/邮箱 + 密码；也支持验证码（演示环境留空）"""
    account: str = Field(..., description="手机号或邮箱")
    password: str = Field(..., description="密码")


class RegisterRequest(BaseModel):
    account: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=64)
    nickname: Optional[str] = None
    sms_code: Optional[str] = Field(None, description="邮箱验证码（注册必填）")


class SendCodeRequest(BaseModel):
    account: str = Field(..., description="邮箱")
    scene: str = Field("register", description="场景: register/login")


class SendCodeResponse(BaseModel):
    sent: bool = True
    dev_code: Optional[str] = Field(None, description="演示模式下返回的验证码（配置 SMTP 后为 None）")
    ttl_seconds: int = 300
    resend_after: int = 60


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserBrief(BaseModel):
    id: int
    nickname: str
    phone: Optional[str] = None
    email: Optional[str] = None
    avatar_text: str = ""
    plan_name: str = "免费版"
    plan_code: str = "free"
    quota_limit: Optional[int] = None
    quota_used: int = 0
    quota_remain: Optional[int] = None
    is_member: bool = False

    model_config = {"from_attributes": True}
