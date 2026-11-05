"""回收站服务：软删除数据的彻底清理与过期自动删除"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    InterviewMessage, InterviewQuestion, InterviewReport, InterviewSession,
    QuestionEvaluation, Resume, ResumeExperience, UserQuestionHistory,
)

RETENTION_DAYS = 7  # 回收站保留天数


def purge_resume(db: Session, resume: Resume) -> None:
    """彻底删除简历及其经历（显式删子表，兼容历史建表无级联）"""
    db.query(ResumeExperience).filter(ResumeExperience.resume_id == resume.id).delete(
        synchronize_session=False
    )
    db.delete(resume)


def purge_session(db: Session, session_id: int) -> None:
    """彻底删除面试会话及全部子表数据（题目/消息/逐题评估/出题历史/报告）

    注意：interview_questions.parent_question_id 存在自引用外键 fk_q_parent，
    直接整表 DELETE 会触发 1451 约束冲突，必须先把引用置空。
    """
    db.query(QuestionEvaluation).filter(QuestionEvaluation.session_id == session_id).delete(
        synchronize_session=False
    )
    db.query(UserQuestionHistory).filter(UserQuestionHistory.session_id == session_id).delete(
        synchronize_session=False
    )
    db.query(InterviewMessage).filter(InterviewMessage.session_id == session_id).delete(
        synchronize_session=False
    )
    # 先解除题目间的追问引用，再删除题目
    db.query(InterviewQuestion).filter(InterviewQuestion.session_id == session_id).update(
        {InterviewQuestion.parent_question_id: None}, synchronize_session=False
    )
    db.query(InterviewQuestion).filter(InterviewQuestion.session_id == session_id).delete(
        synchronize_session=False
    )
    db.query(InterviewReport).filter(InterviewReport.session_id == session_id).delete(
        synchronize_session=False
    )
    db.query(InterviewSession).filter(InterviewSession.id == session_id).delete(
        synchronize_session=False
    )


def purge_expired(db: Session) -> int:
    """清理回收站中超过保留期的数据，返回清理数量（简历数+会话数）"""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    count = 0

    expired_resumes = db.query(Resume).filter(
        Resume.deleted_at.isnot(None), Resume.deleted_at < cutoff
    ).all()
    for resume in expired_resumes:
        purge_resume(db, resume)
        count += 1

    expired_sessions = db.query(InterviewSession).filter(
        InterviewSession.deleted_at.isnot(None), InterviewSession.deleted_at < cutoff
    ).all()
    for sess in expired_sessions:
        purge_session(db, sess.id)
        count += 1

    if count:
        db.commit()
    return count
