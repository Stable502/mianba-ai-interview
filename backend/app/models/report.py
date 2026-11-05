"""诊断报告域与题库域模型"""
from datetime import datetime

from sqlalchemy import (
    BigInteger, Column, DateTime, DECIMAL, ForeignKey, Integer, JSON, SmallInteger,
    String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from app.database import Base


class QuestionEvaluation(Base):
    __tablename__ = "question_evaluations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(BigInteger, ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False)
    content_score = Column(DECIMAL(3, 1), nullable=True, comment="内容质量1-5")
    logic_score = Column(DECIMAL(3, 1), nullable=True, comment="表达逻辑1-5")
    match_score = Column(DECIMAL(3, 1), nullable=True, comment="岗位匹配度1-5")
    delivery_score = Column(DECIMAL(3, 1), nullable=True, comment="沟通气场1-5")
    comment = Column(MEDIUMTEXT, nullable=True, comment="AI点评")
    improved_answer = Column(MEDIUMTEXT, nullable=True, comment="改进后话术示范")
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class InterviewReport(Base):
    __tablename__ = "interview_reports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    is_full = Column(SmallInteger, nullable=False, default=0, comment="1完整版(会员) 0简版(免费)")
    overall_score = Column(DECIMAL(4, 1), nullable=False, comment="综合评分")
    strengths = Column(JSON, nullable=True, comment="优势项数组")
    weaknesses = Column(JSON, nullable=True, comment="短板项数组")
    jd_match = Column(JSON, nullable=True, comment="JD要求逐条对照结果")
    summary = Column(MEDIUMTEXT, nullable=True, comment="总评")
    pdf_url = Column(String(512), nullable=True, comment="导出PDF地址")
    generated_at = Column(DateTime, nullable=False, default=datetime.now)

    session = relationship("InterviewSession")


class QuestionBank(Base):
    __tablename__ = "question_bank"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    interview_type = Column(String(16), nullable=False, comment="tech/behavioral/case/hr")
    job_category = Column(String(32), nullable=False, comment="岗位大类")
    difficulty = Column(String(16), nullable=False, default="mid")
    question_text = Column(Text, nullable=False)
    tags = Column(JSON, nullable=True)
    usage_count = Column(Integer, nullable=False, default=0, comment="被引用次数")
    is_active = Column(SmallInteger, nullable=False, default=1)


class UserQuestionHistory(Base):
    __tablename__ = "user_question_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    bank_question_id = Column(BigInteger, ForeignKey("question_bank.id"), nullable=False)
    session_id = Column(BigInteger, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
