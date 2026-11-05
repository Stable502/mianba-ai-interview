"""面试会话路由：创建 / 预览 / 对话 / 结束"""
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    InterviewerPersona, InterviewMessage, InterviewQuestion, InterviewReport,
    InterviewSession, JobPosition, Resume, User,
)
from app.schemas.interview import (
    InterviewCreate, InterviewOut, MessageCreate, MessageOut, PlanPreview,
    StartInterviewResponse,
)
from app.services import interview_engine
from app.services.quota import can_interview, consume_quota
from app.services.report_engine import generate_report

router = APIRouter(prefix="/api/interviews", tags=["面试会话"])


def _serialize_session(s: InterviewSession) -> InterviewOut:
    data = InterviewOut.model_validate(s).model_dump()
    data["persona_name"] = s.persona.name if s.persona else None
    data["position_title"] = s.job_position.position_title if s.job_position else None
    data["resume_title"] = s.resume.title if s.resume else None
    return InterviewOut(**data)


@router.post("/preview", response_model=PlanPreview)
def preview(
    payload: InterviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成面试方案预览（不扣额度、不落库）"""
    persona = db.get(InterviewerPersona, payload.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="面试官人设不存在")

    # 校验归属
    if payload.resume_id:
        resume = db.get(Resume, payload.resume_id)
        if not resume or resume.user_id != current_user.id or resume.deleted_at is not None:
            raise HTTPException(status_code=400, detail="简历不存在")
    if payload.job_position_id:
        pos = db.get(JobPosition, payload.job_position_id)
        if not pos or pos.user_id != current_user.id:
            raise HTTPException(status_code=400, detail="岗位不存在")

    # 构造临时会话对象用于生成方案
    tmp = InterviewSession(
        id=0, user_id=current_user.id,
        resume_id=payload.resume_id, job_position_id=payload.job_position_id,
        persona_id=payload.persona_id, interview_type=payload.interview_type,
        difficulty=payload.difficulty, planned_minutes=payload.planned_minutes,
    )
    return PlanPreview(**interview_engine.build_plan(db, tmp))


@router.post("", response_model=StartInterviewResponse)
def create_interview(
    payload: InterviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建面试会话：扣减额度、生成开场题"""
    persona = db.get(InterviewerPersona, payload.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="面试官人设不存在")
    if persona.is_premium and persona.is_premium == 1:
        # 演示环境：不强制拦截 premium，仅做提示
        pass

    if payload.resume_id:
        resume = db.get(Resume, payload.resume_id)
        if not resume or resume.user_id != current_user.id or resume.deleted_at is not None:
            raise HTTPException(status_code=400, detail="简历不存在")
    if payload.job_position_id:
        pos = db.get(JobPosition, payload.job_position_id)
        if not pos or pos.user_id != current_user.id:
            raise HTTPException(status_code=400, detail="岗位不存在")

    if not can_interview(db, current_user.id):
        raise HTTPException(status_code=403, detail="本月免费面试额度已用尽，请升级会员")

    session = InterviewSession(
        session_no=f"IV{datetime.now().strftime('%Y%m%d%H%M%S')}{int(time.time() % 100000)}",
        user_id=current_user.id,
        resume_id=payload.resume_id,
        job_position_id=payload.job_position_id,
        persona_id=payload.persona_id,
        interview_type=payload.interview_type,
        difficulty=payload.difficulty,
        planned_minutes=payload.planned_minutes,
        status=2,  # 进行中
        started_at=datetime.now(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # 扣减额度
    consume_quota(db, current_user.id)

    # 生成开场题与面试官开场消息
    opening = interview_engine.generate_opening(db, session)
    opening_msg = InterviewMessage(
        session_id=session.id, question_id=opening.id, role="interviewer",
        content_text=opening.question_text,
    )
    db.add(opening_msg)
    db.commit()
    db.refresh(opening_msg)

    plan = PlanPreview(**interview_engine.build_plan(db, session))
    return StartInterviewResponse(
        session=_serialize_session(session),
        plan=plan,
        opening_message=MessageOut.model_validate(opening_msg),
    )


@router.get("", response_model=list[InterviewOut])
def list_interviews(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """最近面试记录（工作台 / 报告列表）"""
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.created_at.desc())
        .limit(50)
        .all()
    )
    return [_serialize_session(s) for s in sessions]


@router.get("/{session_id}", response_model=InterviewOut)
def get_interview(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = db.get(InterviewSession, session_id)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return _serialize_session(s)


@router.get("/{session_id}/messages", response_model=list[MessageOut])
def list_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = db.get(InterviewSession, session_id)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = (
        db.query(InterviewMessage)
        .filter(InterviewMessage.session_id == session_id)
        .order_by(InterviewMessage.id.asc())
        .all()
    )
    return msgs


@router.post("/{session_id}/messages")
def send_message(
    session_id: int,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """候选人发送回答，返回面试官回应（下一题或追问）"""
    s = db.get(InterviewSession, session_id)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    if s.status not in (2,):
        raise HTTPException(status_code=400, detail="面试已结束")

    # 记录候选人消息
    candidate_msg = InterviewMessage(
        session_id=session_id,
        question_id=payload.question_id,
        role="candidate",
        content_text=payload.content_text,
        duration_ms=payload.duration_ms,
    )
    db.add(candidate_msg)
    db.commit()
    db.refresh(candidate_msg)

    # 生成面试官回应
    next_q = interview_engine.answer_reply(db, s, payload.content_text)
    interviewer_msg = None
    report_id = None
    if next_q:
        interviewer_msg = InterviewMessage(
            session_id=session_id,
            question_id=next_q.id,
            role="interviewer",
            content_text=next_q.question_text,
        )
        db.add(interviewer_msg)
        db.commit()
        db.refresh(interviewer_msg)
    else:
        # 面试自然结束：更新状态并生成诊断报告
        s.status = 3
        s.ended_at = datetime.now()
        db.commit()
        report = generate_report(db, s)
        report_id = report.id

    return {
        "candidate_message": MessageOut.model_validate(candidate_msg),
        "interviewer_message": MessageOut.model_validate(interviewer_msg) if interviewer_msg else None,
        "session_finished": interviewer_msg is None,
        "report_id": report_id,
    }


@router.post("/{session_id}/end")
def end_interview(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """结束面试并生成诊断报告（幂等：重复调用返回已有报告）"""
    s = db.get(InterviewSession, session_id)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="会话不存在")

    if s.status == 2:
        # 进行中 → 用户提前结束
        s.status = 4
        s.ended_at = datetime.now()
        db.commit()
    else:
        # 已结束（自然结束 3 / 提前结束 4）：已有报告直接返回，没有则补生成
        existing = (
            db.query(InterviewReport)
            .filter(InterviewReport.session_id == session_id)
            .order_by(InterviewReport.id.desc())
            .first()
        )
        if existing:
            return {"report_id": existing.id}

    report = generate_report(db, s)
    return {"report_id": report.id}
