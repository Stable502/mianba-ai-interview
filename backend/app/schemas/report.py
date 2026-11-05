"""诊断报告相关 Schema"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EvaluationOut(BaseModel):
    id: int
    question_id: int
    question_text: Optional[str] = None
    content_score: Optional[float] = None
    logic_score: Optional[float] = None
    match_score: Optional[float] = None
    delivery_score: Optional[float] = None
    comment: Optional[str] = None
    improved_answer: Optional[str] = None

    model_config = {"from_attributes": True}


class ReportOut(BaseModel):
    id: int
    session_id: int
    is_full: int
    overall_score: float
    strengths: Optional[list] = None
    weaknesses: Optional[list] = None
    jd_match: Optional[list] = None
    summary: Optional[str] = None
    generated_at: datetime
    # 会话摘要字段
    interview_type: Optional[str] = None
    persona_name: Optional[str] = None
    position_title: Optional[str] = None
    planned_minutes: Optional[int] = None
    session_no: Optional[str] = None
    evaluations: list[EvaluationOut] = []

    model_config = {"from_attributes": True}


class PlanOut(BaseModel):
    id: int
    code: str
    name: str
    price_cents: int
    period_days: int
    max_interviews_month: Optional[int] = None
    full_report_enabled: int
    pdf_export_enabled: int
    persona_premium: int
    is_active: int

    model_config = {"from_attributes": True}
