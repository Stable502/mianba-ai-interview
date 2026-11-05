"""AI 模拟面试引擎

优先使用 DeepSeek LLM 做智能追问与出题；API Key 未配置时降级为基于规则的 Mock。
"""
import asyncio
import random
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import InterviewSession, InterviewQuestion, InterviewMessage, JobPosition, Resume
from app.services import llm_client

# 面试类型中文标签
INTERVIEW_TYPE_NAMES = {
    "tech": "技术岗专业面",
    "behavioral": "行为面·综合面",
    "case": "案例面·管理面",
    "hr": "HR面·薪资谈判",
}

# 各面试类型主干题模板（{} 由简历/JD 上下文插值）
MAIN_QUESTIONS = {
    "tech": [
        "请介绍一下你最近负责的{project}，重点讲清技术架构与关键设计决策。",
        "在{tech}方向，你遇到过的最大技术难点是什么？最终如何解决？",
        "针对{project}，你如何保证高可用、高性能与稳定性？",
        "如果让你重新设计一次{project}，你会做哪些改进？",
    ],
    "behavioral": [
        "请用 STAR 法则，讲讲你最有成就感的一段工作经历。",
        "讲一次你在团队协作中遇到冲突的经历，你是如何处理的？",
        "为什么考虑离开当前公司？你期望下一份工作是什么样的？",
        "你最大的优点和缺点分别是什么？请举例说明。",
    ],
    "case": [
        "假设你是团队负责人，接到一个{project}类业务目标，你会如何拆解并推进落地？",
        "如果项目上线后核心指标连续两周下滑，你会如何定位与应对？",
        "请设计一个{tech}相关的团队管理或业务增长方案，并说明优先级。",
    ],
    "hr": [
        "你的期望薪资是多少？这个预期的依据是什么？",
        "你的离职原因是什么？如何评价上一家公司？",
        "你的职业规划是怎样的？未来 3 年希望达到什么状态？",
        "你还有什么想问我们的吗？",
    ],
}

# STAR 追问链维度（顺序深挖）
STAR_DIMENSIONS = ["background", "task", "action", "result"]

STAR_FOLLOWUP_TEXTS = {
    "background": "能否先说说这件事的背景和目标，为什么它值得做？",
    "task": "你个人在其中承担的核心任务和职责是什么？",
    "action": "你做过的关键决策是什么？有没有备选方案？为什么最终选择这个？",
    "result": "最终结果如何？有没有可量化的收益指标？你沉淀了什么方法论？",
}

# 开场题
OPENING_TEXT = "你好，欢迎参加本次模拟面试。请先用 2-3 分钟简单介绍一下你自己，并重点说说最近一段工作经历。"
CLOSING_TEXT = "感谢你今天的分享。最后，你还有什么问题想问我，或者有什么需要补充的吗？"


# ============ 无意义回复检测与降级回复池 ============

def _detect_nonsense(answer_text: str) -> str:
    """对回答做启发式分类，返回类型标签；有效回答返回 'ok'"""
    if not answer_text or not answer_text.strip():
        return "nonsense_empty"
    text = answer_text.strip()
    if len(text) <= 1:
        return "nonsense_empty"

    # 过短的中文敷衍词（嗯、哦、好、行之类）
    dismissive_words = {"嗯", "哦哦", "好的", "好", "行", "可以", "ok", "是的", "对", "啊啊", "嗯嗯"}
    if text.lower() in dismissive_words:
        return "nonsense_refuse"

    # 重复字符（如 啊啊啊、test test test、好好好）— 优先检测
    if re.search(r"(.)\1{3,}", text) or re.search(r"(\w+)\s+\1\s+\1", text.lower()):
        return "nonsense_repeat"

    # 纯数字（含小数点/负号）
    if re.fullmatch(r"[\d\s.\-+]+", text):
        return "nonsense_chars"

    # 纯字母/键盘乱码（无中文、无空格分隔的有效英文单词）
    if re.fullmatch(r"[a-zA-Z\s]+", text):
        words = text.lower().split()
        common_words = {"the", "is", "a", "an", "test", "hi", "hello", "ok", "yes", "no", "好", "嗯"}
        # 如果只有字母且全是测试/问候词，或者是连续键盘乱码（>=5 个连续字母无空格）
        if all(w in common_words for w in words) or re.search(r"[a-z]{5,}", text.lower().replace(" ", "")):
            if any(w in words for w in ("test", "hi", "hello")):
                return "nonsense_test"
            return "nonsense_chars"
        if len(words) == 1 and len(words[0]) <= 3:
            return "nonsense_test"
        return "ok"

    # 混合但无意义：数字+字母，且总长度 < 15
    if re.fullmatch(r"[a-zA-Z0-9\s]+", text) and len(text) < 15:
        return "nonsense_chars"

    # 拒绝/敷衍关键词（不限制长度，只要命中即视为 refuse）
    refuse_words = ["不知道", "不会", "忘了", "没什么好说", "没什么可说", "不想回答", "不记得", "不清楚", "不了解", "不太清楚", "不太了解"]
    if any(w in text for w in refuse_words):
        return "nonsense_refuse"

    # 过短（< 5 字且无实质内容）
    if len(text) < 5 and not re.search(r"[\u4e00-\u9fff]", text):
        return "nonsense_empty"

    return "ok"


# 每类无意义的多个备选回复（随机选，避免重复）
NONSENSE_REPLY_POOL: dict[str, list[str]] = {
    "nonsense_chars": [
        "看起来可能是输入时按错了键盘，请用完整的句子重新回答一下。",
        "好像出现了输入问题，能麻烦你重新组织一下语言吗？",
        "这似乎不是完整的回答，请再试着说说你的想法。",
    ],
    "nonsense_repeat": [
        "看起来你可能在测试输入，请试着用完整句子作答。",
        "我收到的内容似乎是重复的，能重新说一下吗？",
    ],
    "nonsense_test": [
        "请认真参与面试，用几句话正式回答这个问题。",
        "好的，测试收到了。现在能开始正式作答吗？",
    ],
    "nonsense_offtopic": [
        "嗯，不过我们先聚焦在面试上吧。请回答一下刚才的问题。",
        "话题可以之后再聊，先说说你的工作经历好吗？",
    ],
    "nonsense_refuse": [
        "没关系，随便说一点你想到的就行，比如你最近在用什么技术？",
        "不用紧张，哪怕只说一句话也可以。你最近一份工作做了什么？",
        "理解，那我们换个简单的：你平时最熟悉的技术栈是什么？",
    ],
    "nonsense_empty": [
        "好像没有收到内容，能再试一次吗？用几句话介绍一下你自己就行。",
        "请试着回答一下，任何你想到的都可以。",
    ],
}

# 连续 2 次无意义时的升级回复
NONSENSE_ESCALATION_REPLY = (
    "我注意到你连续两次没有给出有效回答。如果你还没准备好，可以稍后再来。"
    "如果你想继续，请认真用完整句子回答我的问题。"
)


def _count_recent_nonsense(db: Session, session: InterviewSession, window: int = 4) -> int:
    """最近 window 条候选人消息中，被判定为无意义的条数"""
    msgs = (
        db.query(InterviewMessage)
        .filter(
            InterviewMessage.session_id == session.id,
            InterviewMessage.role == "candidate",  # 注意：实际角色名是 candidate
        )
        .order_by(InterviewMessage.id.desc())
        .limit(window)
        .all()
    )
    count = 0
    for m in msgs:
        if _detect_nonsense(m.content_text or "") != "ok":
            count += 1
    return count


def _fallback_reply(answer_text: str, consecutive_nonsense: int) -> Optional[str]:
    """当 LLM 不可用时，用 nonsense 检测 + 预设回复池生成回复"""
    category = _detect_nonsense(answer_text)
    if category == "ok":
        return None  # 有效回答 → 交给 next_question 规则推进

    if consecutive_nonsense >= 2:
        return NONSENSE_ESCALATION_REPLY

    pool = NONSENSE_REPLY_POOL.get(category, NONSENSE_REPLY_POOL["nonsense_empty"])
    return random.choice(pool)

# 根据时长决定主干题数量
def _main_count(minutes: int) -> int:
    if minutes <= 15:
        return 2
    if minutes <= 30:
        return 3
    return 4


def _extract_context(db: Session, session: InterviewSession) -> dict:
    """从简历与 JD 中抽取用于插值题目的上下文"""
    project = "你的核心项目"
    tech = "你熟悉的领域"
    company = ""
    highlights: list[str] = []

    if session.resume_id:
        resume = db.get(Resume, session.resume_id)
        if resume:
            if resume.experiences:
                exp = resume.experiences[0]
                company = exp.company or ""
                project = (exp.title or exp.company or "你的核心项目")
                if exp.tech_stack:
                    tech = "、".join(exp.tech_stack[:3])
                for h in (exp.highlights or [])[:3]:
                    highlights.append(str(h))
            if not highlights and resume.raw_text:
                highlights = ["深挖简历中的项目经历与成果"]

    position_title = ""
    if session.job_position_id:
        pos = db.get(JobPosition, session.job_position_id)
        if pos:
            position_title = pos.position_title or ""

    return {
        "project": project,
        "tech": tech,
        "company": company,
        "position_title": position_title,
        "highlights": highlights,
    }


def build_plan(db: Session, session: InterviewSession) -> dict:
    """生成面试方案预览：考察重点 + 题目结构时间线"""
    ctx = _extract_context(db, session)
    itype = session.interview_type

    focus_map = {
        "tech": ["技术架构", "高可用设计", "性能优化", "故障排查", "系统设计", "团队协作"],
        "behavioral": ["STAR 结构表达", "项目深挖", "离职原因", "协作冲突", "优缺点认知"],
        "case": ["业务拆解", "目标管理", "方案设计", "风险应对", "团队管理"],
        "hr": ["薪资期望", "离职原因", "职业规划", "反问环节", "offer 沟通"],
    }
    focus_points = list(focus_map.get(itype, focus_map["behavioral"]))
    # 若简历有亮点，前置补充为考察重点
    for h in ctx["highlights"]:
        tag = h if len(str(h)) <= 12 else str(h)[:12] + "…"
        if tag not in focus_points:
            focus_points.insert(0, tag)

    minutes = session.planned_minutes
    open_end = min(3, minutes // 5)
    closing_start = max(minutes - 5, open_end)
    timeline = [
        {"time": f"0 — {open_end} 分钟", "title": "开场破冰", "desc": "轻松寒暄，建立对话节奏"},
        {"time": f"{open_end} — {closing_start} 分钟", "title": "核心提问", "desc": "围绕简历与 JD 逐层深挖"},
        {"time": f"{closing_start} — {minutes} 分钟", "title": "反问收尾", "desc": "解答候选人疑问并总结"},
    ]
    main_n = _main_count(minutes)
    return {
        "focus_points": focus_points,
        "timeline": timeline,
        "question_count_range": f"{main_n} — {main_n + 2} 题",
    }


def _create_question(
    db: Session,
    session: InterviewSession,
    seq_no: int,
    qtype: str,
    text: str,
    source: str = "mixed",
    parent_id: Optional[int] = None,
    dimension: Optional[str] = None,
) -> InterviewQuestion:
    q = InterviewQuestion(
        session_id=session.id,
        parent_question_id=parent_id,
        seq_no=seq_no,
        question_type=qtype,
        question_text=text,
        source=source,
        target_dimension=dimension,
        asked_at=datetime.now(),
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


def generate_opening(db: Session, session: InterviewSession) -> InterviewQuestion:
    """生成开场题（seq_no=1）"""
    return _create_question(db, session, 1, "opening", OPENING_TEXT, source="mixed")


def next_question(db: Session, session: InterviewSession) -> Optional[InterviewQuestion]:
    """根据当前会话已出题目，决定并创建下一题；面试结束时返回 None"""
    ctx = _extract_context(db, session)
    itype = session.interview_type
    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.session_id == session.id)
        .order_by(InterviewQuestion.seq_no.asc())
        .all()
    )
    if not questions:
        return generate_opening(db, session)

    last = questions[-1]
    main_count = sum(1 for q in questions if q.question_type == "main")
    target_main = _main_count(session.planned_minutes)

    # 已进入收尾阶段
    if any(q.question_type == "closing" for q in questions):
        return None

    if last.question_type == "closing":
        return None

    # 最后一个 main 题之后若已无追问，进入收尾
    if main_count >= target_main and last.question_type in ("main", "followup"):
        # 若还有追问维度未问完（最多 2 层），先补追问
        followup_done = _count_followups_for(questions, last.parent_question_id or last.id)
        if followup_done < 2 and last.question_type == "main":
            dim = STAR_DIMENSIONS[followup_done]
            return _create_question(
                db, session, last.seq_no + 1, "followup",
                STAR_FOLLOWUP_TEXTS[dim], source="mixed", parent_id=last.id, dimension=dim,
            )
        return _create_question(db, session, last.seq_no + 1, "closing", CLOSING_TEXT, source="mixed")

    # 尚未问够主干题
    if last.question_type == "opening" or main_count < target_main:
        if last.question_type == "main":
            followup_done = _count_followups_for(questions, last.id)
            if followup_done < 2:
                dim = STAR_DIMENSIONS[followup_done]
                return _create_question(
                    db, session, last.seq_no + 1, "followup",
                    STAR_FOLLOWUP_TEXTS[dim], source="mixed", parent_id=last.id, dimension=dim,
                )
        template = MAIN_QUESTIONS[itype][main_count % len(MAIN_QUESTIONS[itype])]
        text = template.format(**ctx)
        return _create_question(db, session, last.seq_no + 1, "main", text, source="mixed")

    return None


def _count_followups_for(questions: list[InterviewQuestion], parent_id: int) -> int:
    return sum(1 for q in questions if q.question_type == "followup" and q.parent_question_id == parent_id)


def _collect_conversation(db: Session, session: InterviewSession) -> list[dict]:
    """收集最近几轮对话历史，供 LLM 做追问决策"""
    msgs = (
        db.query(InterviewMessage)
        .filter(InterviewMessage.session_id == session.id)
        .order_by(InterviewMessage.id.desc())
        .limit(8)
        .all()
    )
    msgs.reverse()
    return [
        {"role": m.role, "content": m.content_text or ""}
        for m in msgs
    ]


def answer_reply(db: Session, session: InterviewSession, answer_text: str) -> Optional[InterviewQuestion]:
    """根据候选人回答，智能生成面试官回应（追问 / 下一题 / 收尾）

    优先使用 DeepSeek LLM 分析回答质量决定策略；不可用时降级为规则推进。
    """
    # 先获取当前会话状态（已出题目数、最后一题类型）
    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.session_id == session.id)
        .order_by(InterviewQuestion.seq_no.asc())
        .all()
    )

    # 已结束
    if not questions or any(q.question_type == "closing" for q in questions):
        return None

    last_q = questions[-1]

    # 检测连续无意义回复数（LLM 不可用时的降级依据，也用于日志）
    recent_nonsense = _count_recent_nonsense(db, session)
    answer_category = _detect_nonsense(answer_text)
    print(f"[Interview] answer_reply: category={answer_category}, recent_nonsense={recent_nonsense}")

    # 尝试 LLM 智能追问
    llm_decision = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            llm_decision = loop.run_until_complete(
                llm_client.interview_reply(
                    question_text=last_q.question_text,
                    answer_text=answer_text,
                    conversation_history=_collect_conversation(db, session),
                    interview_type=session.interview_type,
                )
            )
        finally:
            loop.close()
    except Exception as e:
        print(f"[Interview] LLM 追问调用异常: {e}")

    # LLM 给出了决策
    if llm_decision and llm_decision.get("reply_text"):
        action = llm_decision.get("action", "followup")
        reply_text = llm_decision["reply_text"]

        # 连续 2 次以上 nonsense：无论 LLM 说什么，强制升级语气
        if recent_nonsense >= 2 and answer_category != "ok":
            reply_text = NONSENSE_ESCALATION_REPLY
            action = "closing"

        print(f"[Interview] LLM path: action={action}, reply={reply_text[:60]}...")

        if action == "closing":
            return _create_question(
                db, session, last_q.seq_no + 1, "closing",
                CLOSING_TEXT if recent_nonsense < 2 else reply_text,
                source="llm",
            )

        if action == "followup":
            return _create_question(
                db, session, last_q.seq_no + 1, "followup",
                reply_text, source="llm", parent_id=last_q.id,
                dimension=llm_decision.get("reason", "")[:20] or None,
            )

        # next_question：LLM 引导过渡到下一题，同时用规则决定下一题内容
        next_q_rule = _determine_next_main_question(db, session, questions)
        if next_q_rule:
            # 把 LLM 的引导话术作为下一题的前缀
            combined_text = f"{reply_text}\n\n{next_q_rule.question_text}"
            return _create_question(
                db, session, last_q.seq_no + 1, next_q_rule.question_type,
                combined_text, source="llm", parent_id=next_q_rule.parent_question_id,
                dimension=next_q_rule.target_dimension,
            )
        # 规则也没下一题了，收尾
        return _create_question(
            db, session, last_q.seq_no + 1, "closing",
            CLOSING_TEXT, source="llm",
        )

    # ========== LLM 不可用时的高质量降级 ==========
    print("[Interview] LLM 不可用，走降级路径")

    # 先用 nonsense 检测 + 预设回复池
    fallback = _fallback_reply(answer_text, recent_nonsense)
    if fallback:
        print(f"[Interview] fallback nonsense reply: {fallback[:60]}...")
        return _create_question(
            db, session, last_q.seq_no + 1, "followup",
            fallback, source="fallback_nonsense", parent_id=last_q.id,
        )

    # 有效回答 → 按规则推进到下一题
    return next_question(db, session)


def _determine_next_main_question(
    db: Session,
    session: InterviewSession,
    existing_questions: list[InterviewQuestion],
) -> Optional[InterviewQuestion]:
    """复用 next_question 的逻辑，但返回 Question 对象而非落库"""
    ctx = _extract_context(db, session)
    itype = session.interview_type
    main_count = sum(1 for q in existing_questions if q.question_type == "main")
    target_main = _main_count(session.planned_minutes)
    last = existing_questions[-1]

    if last.question_type == "closing":
        return None
    if main_count >= target_main:
        return None

    template = MAIN_QUESTIONS[itype][main_count % len(MAIN_QUESTIONS[itype])]
    text = template.format(**ctx)
    # 构造一个临时 Question 对象供 answer_reply 使用
    return InterviewQuestion(
        question_type="main",
        question_text=text,
        parent_question_id=None,
        target_dimension=None,
    )
