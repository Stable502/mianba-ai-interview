"""诊断报告路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    InterviewQuestion, InterviewReport, InterviewSession,
    QuestionEvaluation, User,
)
from app.schemas.report import EvaluationOut, ReportOut

router = APIRouter(prefix="/api/reports", tags=["诊断报告"])


def _build_report_out(report: InterviewReport) -> ReportOut:
    session: InterviewSession = report.session
    data = ReportOut.model_validate(report).model_dump()
    if session:
        data["interview_type"] = session.interview_type
        data["persona_name"] = session.persona.name if session.persona else None
        data["position_title"] = session.job_position.position_title if session.job_position else None
        data["planned_minutes"] = session.planned_minutes
        data["session_no"] = session.session_no
    return ReportOut(**data)


@router.get("", response_model=list[ReportOut])
def list_reports(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """报告列表（排除回收站中的记录）"""
    reports = (
        db.query(InterviewReport)
        .join(InterviewSession, InterviewReport.session_id == InterviewSession.id)
        .filter(
            InterviewReport.user_id == current_user.id,
            InterviewSession.deleted_at.is_(None),
        )
        .order_by(InterviewReport.generated_at.desc())
        .all()
    )
    return [_build_report_out(r) for r in reports]


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.get(InterviewReport, report_id)
    if (
        not report
        or report.user_id != current_user.id
        or (report.session and report.session.deleted_at is not None)
    ):
        raise HTTPException(status_code=404, detail="报告不存在")

    result = _build_report_out(report)

    # 逐题评估（附带题目文本）
    evals = (
        db.query(QuestionEvaluation)
        .filter(QuestionEvaluation.session_id == report.session_id)
        .order_by(QuestionEvaluation.id.asc())
        .all()
    )
    questions = {
        q.id: q for q in
        db.query(InterviewQuestion).filter(InterviewQuestion.session_id == report.session_id).all()
    }
    eval_list = []
    for e in evals:
        d = EvaluationOut.model_validate(e).model_dump()
        q = questions.get(e.question_id)
        d["question_text"] = q.question_text if q else None
        eval_list.append(EvaluationOut(**d))
    result.evaluations = eval_list
    return result


@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除面试记录：移入回收站（软删除会话，7天后自动清理，可恢复）"""
    from datetime import datetime

    report = db.get(InterviewReport, report_id)
    if not report or report.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="报告不存在")
    session = report.session
    if session:
        session.deleted_at = datetime.now()
        db.commit()
    return {"deleted": True}
