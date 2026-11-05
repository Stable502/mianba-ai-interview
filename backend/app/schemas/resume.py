"""简历与岗位 Schema"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ResumeExperienceIn(BaseModel):
    exp_type: str = Field(default="project", description="work/project/education")
    company: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    tech_stack: Optional[list] = None
    description: Optional[str] = None
    highlights: Optional[list] = None
    sort_order: int = 0


class ResumeExperienceOut(ResumeExperienceIn):
    id: int
    # ORM 返回 date 对象, 输出模型必须用 date 而非 str, 否则序列化报错(500)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    model_config = {"from_attributes": True}


class ResumeCreate(BaseModel):
    title: str = Field(..., description="版本名")
    raw_text: Optional[str] = None
    file_url: Optional[str] = None
    experiences: list[ResumeExperienceIn] = []


class ResumeUpdate(BaseModel):
    title: Optional[str] = None
    raw_text: Optional[str] = None
    is_default: Optional[int] = None
    experiences: Optional[list[ResumeExperienceIn]] = None


class ResumeOut(BaseModel):
    id: int
    title: str
    file_url: Optional[str] = None
    raw_text: Optional[str] = None
    is_default: int
    created_at: datetime
    experiences: list[ResumeExperienceOut] = []

    model_config = {"from_attributes": True}


class PositionCreate(BaseModel):
    company_name: Optional[str] = None
    position_title: str
    jd_text: str
    job_category: Optional[str] = None
    source: str = "paste"


class PositionOut(BaseModel):
    id: int
    company_name: Optional[str] = None
    position_title: str
    jd_text: str
    job_category: Optional[str] = None
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PersonaOut(BaseModel):
    id: int
    code: str
    name: str
    description: str
    is_premium: int
    is_active: int
    voice_config: Optional[dict] = None

    model_config = {"from_attributes": True}
