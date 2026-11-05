"""AI 诊断报告引擎

优先使用 DeepSeek LLM 做多维度评分与点评；API Key 未配置时降级为基于规则的
确定性评分（不再给垃圾文本打高分）。
"""
import asyncio
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    InterviewMessage, InterviewQuestion, InterviewReport, InterviewSession,
    QuestionEvaluation, JobPosition,
)
from app.services import llm_client

# 结构化表达提示词（用于规则降级时的逻辑判断）
LOGIC_HINTS = ["首先", "其次", "然后", "最后", "因为", "所以", "目标", "结果",
               "背景", "任务", "行动", "结论", "具体来说", "一方面", "另一方面", "总结",
               "第一", "第二", "第三", "综上所述", "基于"]

# 明显无效/跑题的回答特征（用于识别垃圾回答）
GIBBERISH_PATTERNS = [
    r"^(不知道|不清楚|不会|没想过|随便|都行|无所谓)$",
    r"^[a-zA-Z]{1,5}$",  # 单个英文词
    r"^[\W_]+$",  # 纯标点/符号
    r"^(asdf|qwer|test|测试|哈哈|嗯嗯|好的|OK|ok|好)$",
    r"我(觉得|认为).{0,4}对",
    r".{0,3}(吧|呢|啊|呀|哦)$",  # 极短语气词
]


def _is_gibberish(text: str) -> bool:
    """判断回答是否为无效/跑题/垃圾文本"""
    t = (text or "").strip()
    if len(t) <= 6:
        return True
    # 检查是否大部分为无意义重复字符
    if len(set(t.replace(" ", ""))) <= 3:
        return True
    for pat in GIBBERISH_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return True
    return False


def _rule_based_score(text: str) -> dict:
    """基于规则的确定性评分（仅在 LLM 不可用时降级使用）

    关键改变：不再给所有回答一个 3.6 的基底分，而是：
    - 垃圾文本 -> 低分给 1.5-2.0
    - 极短回答 -> 中低分给 2.0-2.5
    - 有实质内容 -> 按长度和结构给分，但封顶 4.5
    """
    t = (text or "").strip()

    # 垃圾/无效回答
    if _is_gibberish(t):
        return {
            "content_score": 1.5,
            "logic_score": 1.5,
            "match_score": 1.5,
            "delivery_score": 2.0,
            "comment": "回答内容过短或未针对问题作答，建议认真思考后给出实质性回答。",
            "improved_answer": None,
        }

    length = len(t)
    logic_hits = sum(1 for w in LOGIC_HINTS if w in t)

    # 词数估算（中文按字算）
    word_count = length

    # 内容分：有实质内容才给高分
    if word_count < 30:
        content = 2.2
    elif word_count < 80:
        content = 2.8
    elif word_count < 200:
        content = 3.4
    else:
        content = 4.0

    # 逻辑分：结构提示词命中越多越高
    logic = 2.5 + min(logic_hits * 0.3, 2.0)
    logic = min(logic, 4.5)

    # 匹配分：默认中等，内容长且有结构则偏高
    match = 3.0 + min(word_count / 600, 0.8)
    match = min(match, 4.3)

    # 表达分：长度适中且有结构的给较高表达分
    delivery = 2.8 + min(logic_hits * 0.2, 1.2) + min(word_count / 800, 0.5)
    delivery = min(delivery, 4.2)

    good_points = []
    weak_points = []
    if word_count >= 80:
        good_points.append("回答篇幅充足，展示了具体内容")
    else:
        weak_points.append("回答篇幅偏短，建议补充更多细节")
    if logic_hits >= 2:
        good_points.append("使用了结构化表达（如 STAR/层次词）")
    else:
        weak_points.append("逻辑结构不够清晰，建议使用 STAR 等结构化方法")
    if word_count >= 200:
        good_points.append("内容详实，有一定案例支撑")
    else:
        weak_points.append("缺少具体案例与量化数据")

    comment = (
        "✅ 答得好的地方：" + ("；".join(good_points) if good_points else "候选人态度认真，已尝试作答") + "\n"
        + "⚠️ 欠缺/待改进：" + ("；".join(weak_points) if weak_points else "继续保持，可在更高难度场景下挑战自己")
    )

    return {
        "content_score": round(content, 1),
        "logic_score": round(logic, 1),
        "match_score": round(match, 1),
        "delivery_score": round(delivery, 1),
        "comment": comment,
        "improved_answer": "参考标准答案（STAR 结构）：先描述问题背景与目标（Situation/Task），再说明关键决策与行动（Action），最后用可量化结果收尾（Result）。",
    }


async def _score_single_answer(
    question_text: str,
    answer_text: str,
    interview_type: str,
) -> dict:
    """对单道回答评分：优先 LLM（带一次重试），失败降级规则"""
    if not (answer_text or "").strip():
        return {
            "content_score": 1.0, "logic_score": 1.0,
            "match_score": 1.0, "delivery_score": 1.5,
            "comment": "✅ 答得好的地方：无（候选人未作答）。\n⚠️ 欠缺/待改进：本题未给出回答，建议针对该题型加强练习，准备至少一个可量化的项目案例。",
            "improved_answer": "参考标准答案（STAR 结构）：先描述问题背景与目标（Situation/Task），再说明关键决策与行动（Action），最后用可量化结果收尾（Result）。",
        }

    # LLM 评分，失败重试一次（批量并发时可能触发限流）
    for attempt in range(2):
        llm_result = await llm_client.interview_score(
            question_text=question_text,
            answer_text=answer_text,
            interview_type=interview_type,
        )
        if llm_result:
            return llm_result
        if attempt == 0:
            await asyncio.sleep(1)

    # LLM 不可用时降级
    return _rule_based_score(answer_text)


def generate_report(db: Session, session: InterviewSession) -> InterviewReport:
    """为一场已结束的面试生成完整诊断报告

    使用事件循环调用 async LLM 评分；在 FastAPI 同步端点中安全运行。
    """
    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.session_id == session.id)
        .order_by(InterviewQuestion.seq_no.asc())
        .all()
    )

    # 按对话顺序配对问答：候选人消息归属其前面最近的一条面试官提问
    # （兼容 question_id 为空的历史消息，以及同一题多条回答的情况）
    msgs = (
        db.query(InterviewMessage)
        .filter(InterviewMessage.session_id == session.id)
        .order_by(InterviewMessage.id.asc())
        .all()
    )
    answer_map: dict = {}
    current_qid = None
    for m in msgs:
        if m.role == "interviewer":
            if m.question_id:
                current_qid = m.question_id
        elif m.role == "candidate" and m.content_text:
            if current_qid:
                prev = answer_map.get(current_qid)
                answer_map[current_qid] = f"{prev} {m.content_text}".strip() if prev else m.content_text

    # 收集所有待评分的（问题，回答）对
    pairs = []
    for q in questions:
        pairs.append((q, answer_map.get(q.id, "")))

    # 批量调用 LLM 评分（限制并发为 3，避免突发限流导致全部降级为规则评分）
    sem = asyncio.Semaphore(3)

    async def _bounded(q, ans, itype):
        async with sem:
            return await _score_single_answer(q.question_text, ans, itype)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            scores_list = loop.run_until_complete(
                asyncio.gather(*[
                    _bounded(q, ans, session.interview_type)
                    for q, ans in pairs
                ])
            )
        finally:
            loop.close()
    except Exception as e:
        print(f"[Report] LLM 评分批量调用异常，降级规则评分: {e}")
        scores_list = [_rule_based_score(ans) for _, ans in pairs]

    # 逐题落库
    evaluations = []
    for (q, _), scores in zip(pairs, scores_list):
        ev = QuestionEvaluation(
            session_id=session.id,
            question_id=q.id,
            comment=scores.get("comment", ""),
            improved_answer=scores.get("improved_answer"),
            content_score=scores["content_score"],
            logic_score=scores["logic_score"],
            match_score=scores["match_score"],
            delivery_score=scores["delivery_score"],
        )
        db.add(ev)
        evaluations.append(ev)

    db.flush()

    # 综合评分（所有题目四维平均）
    total = sum(
        (e.content_score + e.logic_score + e.match_score + e.delivery_score) / 4
        for e in evaluations
    )
    overall = round(total / max(len(evaluations), 1), 1)

    # 优势 / 短板 — 根据实际评分生成
    avg_content = sum(e.content_score for e in evaluations) / max(len(evaluations), 1)
    avg_logic = sum(e.logic_score for e in evaluations) / max(len(evaluations), 1)
    avg_match = sum(e.match_score for e in evaluations) / max(len(evaluations), 1)
    avg_delivery = sum(e.delivery_score for e in evaluations) / max(len(evaluations), 1)

    strengths = []
    weaknesses = []

    if avg_content >= 3.5:
        strengths.append("回答内容充实，能结合具体经验展开")
    else:
        weaknesses.append("回答内容偏薄，建议补充具体案例与量化数据")

    if avg_logic >= 3.5:
        strengths.append("表达条理清晰，有较好的结构化思维")
    else:
        weaknesses.append("逻辑结构不够清晰，建议使用 STAR 等结构化方法")

    if avg_match >= 3.5:
        strengths.append("回答紧扣问题，体现了岗位相关能力")
    else:
        weaknesses.append("回答与问题的贴合度有待提升，注意审题")

    if avg_delivery >= 3.5:
        strengths.append("语言表达流畅，专业术语使用准确")
    else:
        weaknesses.append("语言表达可进一步打磨，注意专业术语的准确性")

    if not strengths:
        strengths.append("候选人态度认真，值得肯定")
    if not weaknesses:
        weaknesses.append("继续保持，可在更高难度场景下挑战自己")

    # JD 匹配度（若有目标岗位）
    jd_match = []
    position_title = None
    if session.job_position_id:
        pos = db.get(JobPosition, session.job_position_id)
        if pos:
            position_title = pos.position_title
            jd_match = [
                {"requirement": "岗位核心技能要求", "level": "匹配" if avg_match >= 3.5 else "部分匹配",
                 "gap": "技术栈基本吻合" if avg_match >= 3.5 else "需在相关技能上多做准备"},
                {"requirement": "项目经验要求", "level": "匹配" if avg_content >= 3.5 else "部分匹配",
                 "gap": "建议补充量化成果与规模数据" if avg_content < 3.5 else "项目经验表达较为充分"},
                {"requirement": "软素质 / 协作要求", "level": "匹配" if avg_delivery >= 3.5 else "部分匹配",
                 "gap": "表达流畅度可进一步提升" if avg_delivery < 3.5 else "沟通态度积极"},
            ]

    # 总评
    grade = "优秀" if overall >= 4.2 else "良好" if overall >= 3.3 else "有待提升"
    summary = (
        f"本场{_type_name(session.interview_type)}模拟面试综合表现{grade}。"
        f"综合得分 {overall}（满分 5.0）。"
    )
    if strengths:
        summary += f"你的优势在于：{'、'.join(strengths[:2])}。"
    if weaknesses:
        summary += f"后续建议：{'、'.join(weaknesses[:2])}。"

    report = InterviewReport(
        session_id=session.id,
        user_id=session.user_id,
        is_full=1,
        overall_score=overall,
        strengths=strengths,
        weaknesses=weaknesses,
        jd_match=jd_match,
        summary=summary,
        generated_at=datetime.now(),
    )
    db.add(report)
    db.flush()

    # 回填会话综合分并标记状态
    session.overall_score = overall
    session.status = 3 if session.status in (2,) else session.status
    session.ended_at = datetime.now()
    db.commit()
    db.refresh(report)
    return report


def _report_is_blank(db: Session, session_id: int) -> bool:
    """报告是否为'全部未作答'的坏报告（历史 question_id 配对 bug 产物）"""
    evals = (
        db.query(QuestionEvaluation)
        .filter(QuestionEvaluation.session_id == session_id)
        .all()
    )
    if not evals:
        return True
    # 兼容旧文案"候选人未作答。"与新文案"无（候选人未作答）"
    return all(
        ("未作答" in (e.comment or "")) and (e.content_score or 0) <= 1.1
        for e in evals
    )


def backfill_missing_reports(db: Session) -> int:
    """数据修复（幂等）：
    1. 为已结束但缺少报告的会话补生成报告
    2. 重新生成'全部未作答'的坏报告（仅当会话中实际存在候选人回答时）
    """
    from app.models import (
        InterviewSession as _S, InterviewReport as _R, InterviewMessage as _M,
    )
    ended = db.query(_S).filter(_S.status.in_([3, 4])).all()
    count = 0
    for s in ended:
        report = (
            db.query(_R)
            .filter(_R.session_id == s.id)
            .order_by(_R.id.desc())
            .first()
        )
        has_answers = (
            db.query(_M)
            .filter(
                _M.session_id == s.id,
                _M.role == "candidate",
                _M.content_text.isnot(None),
                _M.content_text != "",
            )
            .first()
            is not None
        )
        if report:
            # 有报告：仅在"坏报告 + 实际有回答"时重新生成（避免无回答会话反复重生成）
            if not (_report_is_blank(db, s.id) and has_answers):
                continue
            db.query(QuestionEvaluation).filter(QuestionEvaluation.session_id == s.id).delete()
            db.query(_R).filter(_R.session_id == s.id).delete()
            db.commit()
        try:
            generate_report(db, s)
            count += 1
            print(f"[Backfill] 会话 {s.id} 报告已{'重新' if report else '补'}生成")
        except Exception as e:
            print(f"[Backfill] 会话 {s.id} 报告生成失败: {e}")
            db.rollback()
    return count


def _type_name(itype: str) -> str:
    return {
        "tech": "技术岗专业面",
        "behavioral": "行为面",
        "case": "案例面",
        "hr": "HR面",
    }.get(itype, "综合")
