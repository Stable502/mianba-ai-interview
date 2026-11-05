"""面试会话域模型"""
from datetime import datetime

from sqlalchemy import (
    BigInteger, Column, DateTime, DECIMAL, ForeignKey, Integer, SmallInteger,
    String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from app.database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_no = Column(String(40), nullable=False, unique=True, comment="业务单号")
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    resume_id = Column(BigInteger, ForeignKey("resumes.id"), nullable=True, comment="可空: 无简历快捷练习")
    job_position_id = Column(BigInteger, ForeignKey("job_positions.id"), nullable=True, comment="可空: 无JD通用练习")
    persona_id = Column(BigInteger, ForeignKey("interviewer_personas.id"), nullable=False)
    interview_type = Column(String(16), nullable=False, comment="tech/behavioral/case/hr")
    difficulty = Column(String(16), nullable=False, default="mid", comment="对标职级")
    planned_minutes = Column(Integer, nullable=False, default=30)
    status = Column(SmallInteger, nullable=False, default=1, comment="1待开始 2进行中 3正常结束 4提前结束 5中断")
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    overall_score = Column(DECIMAL(4, 1), nullable=True, comment="综合评分1-5")
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    deleted_at = Column(DateTime, nullable=True, comment="软删除时间 NULL=未删除（回收站保留7天）")

    persona = relationship("InterviewerPersona")
    resume = relationship("Resume")
    job_position = relationship("JobPosition")
    questions = relationship("InterviewQuestion", back_populates="session", cascade="all, delete-orphan")
    messages = relationship("InterviewMessage", back_populates="session", cascade="all, delete-orphan")


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    parent_question_id = Column(BigInteger, ForeignKey("interview_questions.id"), nullable=True, comment="追问指向的上一题")
    seq_no = Column(Integer, nullable=False, comment="题目在会话中的顺序")
    question_type = Column(String(16), nullable=False, comment="opening/main/followup/closing")
    question_text = Column(Text, nullable=False)
    source = Column(String(16), nullable=False, comment="resume/jd/bank/mixed")
    bank_question_id = Column(BigInteger, nullable=True, comment="来自通用题库时回链")
    target_dimension = Column(String(32), nullable=True, comment="考察维度")
    asked_at = Column(DateTime, nullable=True)

    session = relationship("InterviewSession", back_populates="questions")


class InterviewMessage(Base):
    __tablename__ = "interview_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(BigInteger, ForeignKey("interview_questions.id", ondelete="SET NULL"), nullable=True)
    role = Column(String(16), nullable=False, comment="interviewer/candidate")
    content_text = Column(MEDIUMTEXT, nullable=True, comment="ASR转写或面试官台词")
    audio_url = Column(String(512), nullable=True, comment="录音/合成音频存储地址")
    asr_confidence = Column(DECIMAL(4, 3), nullable=True, comment="识别置信度")
    duration_ms = Column(Integer, nullable=True)
    is_interrupted = Column(SmallInteger, nullable=False, default=0, comment="该消息是否被用户打断")
    manual_revised = Column(SmallInteger, nullable=False, default=0, comment="用户是否手动修正过转写")
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    session = relationship("InterviewSession", back_populates="messages")
