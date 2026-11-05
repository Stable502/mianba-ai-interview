"""DeepSeek LLM 客户端封装

提供两个核心能力：
1. chat() — 通用对话
2. interview_score() — 面试回答多维度评分（输出严格 JSON）
3. interview_reply() — 基于候选人回答的智能追问/回应

当 API Key 未配置时，所有方法返回 None，由调用方做降级处理。
"""
import json
import re
from typing import Optional

import httpx

from app.config import settings


def _is_configured() -> bool:
    return bool(settings.DEEPSEEK_API_KEY)


async def chat(
    messages: list[dict],
    temperature: float = 0.7,
    response_format: Optional[dict] = None,
    timeout: float = 30.0,
) -> Optional[str]:
    """通用 LLM 对话，返回文本内容；失败/未配置时返回 None"""
    if not _is_configured():
        return None
    try:
        payload = {
            "model": settings.DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[LLM] chat 调用失败: {e}")
        return None


# ============ 面试评分 ============

SCORE_SYSTEM_PROMPT = """你是一名资深技术面试官，正在对候选人的回答进行多维度评分。
请严格按照以下四个维度评分，每个维度 1-5 分（1=极差/跑题，2=较差，3=一般，4=良好，5=优秀）：

- content_score（内容质量）: 回答是否有实质内容、具体案例、技术细节或数据支撑
- logic_score（逻辑结构）: 是否有条理、层次清晰、使用 STAR 等结构化表达
- match_score（岗位匹配）: 回答是否紧扣问题要求、是否体现与目标岗位相关的能力
- delivery_score（表达流畅）: 语言是否通顺、专业术语是否准确、是否有冗余

评分标准：
1分 = 完全跑题或胡言乱语（如"不知道""asdfgh""我觉得你说的对"）
2分 = 内容很少，明显跑题或仅一两句
3分 = 有基本回答但缺乏细节和结构
4分 = 回答充实、有结构、有一定案例
5分 = 内容丰富、逻辑严谨、有量化结果、专业度高

请只返回 JSON 对象，不要有任何额外文字：
{
  "content_score": 数字,
  "logic_score": 数字,
  "match_score": 数字,
  "delivery_score": 数字,
  "comment": "对该回答的作答分析，必须包含两段：第一段以'✅ 答得好的地方：'开头，列出回答中表现好的点；第二段以'⚠️ 欠缺/待改进：'开头，指出回答中不足或欠缺的地方。两段之间用换行分隔。整体不超过200字",
  "improved_answer": "针对该面试题的参考标准答案（不是改写候选人回答，而是面试官期望的优秀作答范例），使用 STAR 结构，300字以内"
}"""


async def interview_score(
    question_text: str,
    answer_text: str,
    interview_type: str = "tech",
    timeout: float = 30.0,
) -> Optional[dict]:
    """对一道面试回答做多维度评分，返回 dict；失败时返回 None"""
    if not _is_configured():
        return None

    user_prompt = f"""面试类型: {interview_type}
面试官问题: {question_text}
候选人回答: {answer_text if answer_text else "（候选人未作答或回答为空）"}

请对上述回答进行评分，严格返回 JSON。"""

    messages = [
        {"role": "system", "content": SCORE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw = await chat(messages, temperature=0.3, timeout=timeout)
    if not raw:
        return None

    # 解析 JSON（兼容模型偶尔输出 markdown 代码块）
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 尝试用正则提取 JSON 对象
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return None
        else:
            return None

    # 校验并归一化
    result = {}
    for key in ("content_score", "logic_score", "match_score", "delivery_score"):
        val = data.get(key)
        try:
            val = float(val)
            val = max(1.0, min(5.0, val))
            result[key] = round(val, 1)
        except (TypeError, ValueError):
            result[key] = 3.0  # 缺失时给中等分

    result["comment"] = str(data.get("comment", "")).strip()[:600]
    result["improved_answer"] = str(data.get("improved_answer", "")).strip()[:800]
    return result


# ============ 智能追问 ============

REPLY_SYSTEM_PROMPT = """你是一名专业的AI面试官，正在与候选人进行模拟面试。

第一步：先判断候选人的回答属于以下哪一类（answer_type 字段）：
- "good" — 回答有实质内容、紧扣问题
- "too_short" — 有少量有效信息但非常短，需要展开
- "nonsense_chars" — 随机字符、纯数字、键盘乱码（如 123456、asdfgh、qwertzui）
- "nonsense_repeat" — 重复字符/重复词（如 啊啊啊、好好好、test test test）
- "nonsense_test" — 明显是测试语（如 test、123、hi、hello、在吗）
- "nonsense_offtopic" — 完全跑题/闲聊（如聊天气、吐槽、无关话题）
- "nonsense_refuse" — 明确拒绝回答或消极敷衍（如 不知道、不会、忘了、没什么好说的）
- "nonsense_empty" — 空回答或只有标点/表情

第二步：根据分类决定 reply_text 的语气和策略（reply_text 字段）：
- good → 深入追问某个细节，不要重复已问过的内容
- too_short → 肯定对方说了的部分，然后给具体引导帮他补充
- nonsense_chars → 温和提醒"看起来可能是输入问题"，请他重新作答；如果对话历史里上一次也出现过 nonsense_*，这次要更明确地提示他认真回答
- nonsense_repeat → 提醒"看起来像是重复输入"，请他用完整句子回答
- nonsense_test → 礼貌但直接地请他认真参与面试，正式作答
- nonsense_offtopic → 礼貌地把话题拉回面试问题，不要跟着闲聊
- nonsense_refuse → 表现出理解，给具体的小切口引导（如"没关系，随便说一点你想到的就行""比如你最近用过什么技术栈"），降低对方压力；如果第二次拒绝，建议他稍后准备好再来
- nonsense_empty → 如果对话历史显示他上一次也没答，明确说明需要他配合回答才能继续；否则温和地请他试试

重要：
- 语气要自然多样，不要每次都用"感谢你的回答，不过..."这种模板开头
- 对 nonsense_* 类别，reply_text 不要超过 120 字，直接说重点
- 如果对话历史里已经有 2 次以上 nonsense_*，考虑 action="closing" 结束面试

请严格返回 JSON：
{
  "action": "followup" 或 "next_question" 或 "closing",
  "answer_type": "上述 8 种分类之一",
  "reply_text": "面试官要说的话",
  "reason": "简短说明为什么这样决定（可选，不超过50字）"
}"""


async def interview_reply(
    question_text: str,
    answer_text: str,
    conversation_history: list[dict],
    interview_type: str = "tech",
    timeout: float = 30.0,
) -> Optional[dict]:
    """基于候选人回答生成面试官追问/回应；失败时返回 None"""
    if not _is_configured():
        return None

    history_str = "\n".join(
        f"[{m['role']}] {m['content']}"
        for m in conversation_history[-6:]  # 最近 3 轮
    )

    user_prompt = f"""面试类型: {interview_type}
当前问题: {question_text}
候选人回答: {answer_text}

对话历史:
{history_str}

请决定下一步行动，严格返回 JSON。"""

    messages = [
        {"role": "system", "content": REPLY_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw = await chat(messages, temperature=0.5, timeout=timeout)
    if not raw:
        return None

    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return None
        else:
            return None

    action = data.get("action", "followup")
    if action not in ("followup", "next_question", "closing"):
        action = "followup"

    answer_type = data.get("answer_type", "unknown")

    print(f"[LLM] interview_reply: answer_type={answer_type}, action={action}")

    return {
        "action": action,
        "answer_type": answer_type,
        "reply_text": str(data.get("reply_text", "")).strip()[:300],
        "reason": str(data.get("reason", "")).strip()[:50],
    }
