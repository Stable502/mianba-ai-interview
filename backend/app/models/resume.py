"""面试准备域模型"""
from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Column, Date, DateTime, ForeignKey, Integer, JSON, SmallInteger,
    String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from app.database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    title = Column(String(128), nullable=False, comment="版本名")
    file_url = Column(String(512), nullable=True, comment="原始文件存储地址")
    raw_text = Column(MEDIUMTEXT, nullable=True, comment="解析出的纯文本")
    parsed_json = Column(JSON, nullable=True, comment="结构化解析结果")
    is_default = Column(SmallInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    deleted_at = Column(DateTime, nullable=True, comment="软删除时间 NULL=未删除（回收站保留7天）")

    experiences = relationship(
        "ResumeExperience", back_populates="resume", cascade="all, delete-orphan"
    )


class ResumeExperience(Base):
    __tablename__ = "resume_experiences"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    resume_id = Column(BigInteger, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    exp_type = Column(String(16), nullable=False, comment="work/project/education")
    company = Column(String(128), nullable=True)
    title = Column(String(128), nullable=True, comment="职位/角色")
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True, comment="NULL=至今")
    tech_stack = Column(JSON, nullable=True, comment="技术栈数组")
    description = Column(Text, nullable=True, comment="经历描述")
    highlights = Column(JSON, nullable=True, comment="量化亮点数组")
    sort_order = Column(Integer, nullable=False, default=0)

    resume = relationship("Resume", back_populates="experiences")


class JobPosition(Base):
    __tablename__ = "job_positions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    company_name = Column(String(128), nullable=True)
    position_title = Column(String(128), nullable=False)
    jd_text = Column(MEDIUMTEXT, nullable=False, comment="JD原文")
    parsed_requirements = Column(JSON, nullable=True, comment="解析出的职责/要求/软素质条目")
    job_category = Column(String(32), nullable=True, comment="岗位大类")
    source = Column(String(16), nullable=False, default="paste", comment="paste/link")
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class InterviewerPersona(Base):
    __tablename__ = "interviewer_personas"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(32), nullable=False, unique=True, comment="coach/pressure/bigtech/fast")
    name = Column(String(64), nullable=False)
    description = Column(String(255), nullable=False)
    prompt_template = Column(Text, nullable=False, comment="System Prompt 模板")
    voice_config = Column(JSON, nullable=True, comment="TTS音色/语速配置")
    is_premium = Column(SmallInteger, nullable=False, default=0, comment="会员专属风格")
    is_active = Column(SmallInteger, nullable=False, default=1)
