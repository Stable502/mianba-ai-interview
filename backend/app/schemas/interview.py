"""面试会话相关 Schema"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InterviewCreate(BaseModel):
    resume_id: Optional[int] = None
    job_position_id: Optional[int] = None
    persona_id: int
    interview_type: str = Field(..., description="tech/behavioral/case/hr")
    difficulty: str = "mid"
    planned_minutes: int = 30


class InterviewOut(BaseModel):
    id: int
    session_no: str
    user_id: int
    resume_id: Optional[int] = None
    job_position_id: Optional[int] = None
    persona_id: int
    interview_type: str
    difficulty: str
    planned_minutes: int
    status: int
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    overall_score: Optional[float] = None
    created_at: datetime
    persona_name: Optional[str] = None
    position_title: Optional[str] = None
    resume_title: Optional[str] = None

    model_config = {"from_attributes": True}


class QuestionOut(BaseModel):
    id: int
    session_id: int
    parent_question_id: Optional[int] = None
    seq_no: int
    question_type: str
    question_text: str
    source: str
    target_dimension: Optional[str] = None
    asked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    """候选人发送消息（文本模拟语音转写）"""
    content_text: str
    question_id: Optional[int] = None
    duration_ms: Optional[int] = None


class MessageOut(BaseModel):
    id: int
    session_id: int
    question_id: Optional[int] = None
    role: str
    content_text: Optional[str] = None
    duration_ms: Optional[int] = None
    is_interrupted: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PlanPreview(BaseModel):
    """面试方案预览"""
    focus_points: list[str] = []
    timeline: list[dict] = []
    question_count_range: str = "8 — 10 题"


class StartInterviewResponse(BaseModel):
    session: InterviewOut
    plan: PlanPreview
    opening_message: Optional[MessageOut] = None
