"""数据种子脚本：初始化订阅计划、面试官人设、通用题库

用法：
    python -m app.seed
"""
from app.database import Base, SessionLocal, engine
from app.models import InterviewerPersona, Plan, QuestionBank

# 订阅计划
PLANS = [
    ("free", "免费版", 0, 0, 2, 0, 0, 0),
    ("monthly", "月度会员", 3900, 30, None, 1, 1, 1),
    ("quarterly", "季度会员", 9900, 90, None, 1, 1, 1),
    ("yearly", "年度会员", 29900, 365, None, 1, 1, 1),
]

# 面试官人设
PERSONAS = [
    {
        "code": "coach", "name": "温和教练型",
        "description": "语气友好，多给引导和鼓励，适合建立自信", "is_premium": 0,
        "prompt_template": "你是一位温和耐心的面试教练，多用引导式提问并给予鼓励。",
        "voice_config": {"tone": "warm", "speed": 0.95},
    },
    {
        "code": "pressure", "name": "压力挑战型",
        "description": "高频追问，质疑回答漏洞，模拟高压面试", "is_premium": 0,
        "prompt_template": "你是一位严格挑剔的面试官，会高频追问并质疑回答中的漏洞。",
        "voice_config": {"tone": "sharp", "speed": 1.05},
    },
    {
        "code": "bigtech", "name": "大厂风格",
        "description": "流程严谨，深挖技术与项目细节，对标大厂标准", "is_premium": 1,
        "prompt_template": "你是一位大厂资深面试官，流程严谨，深挖技术细节与项目难点。",
        "voice_config": {"tone": "professional", "speed": 1.0},
    },
    {
        "code": "fast", "name": "快节奏",
        "description": "语速快、单刀直入，考验临场反应", "is_premium": 1,
        "prompt_template": "你是一位雷厉风行的面试官，语速快、提问直接，考验临场反应。",
        "voice_config": {"tone": "fast", "speed": 1.2},
    },
]

# 通用题库（兜底题源）
BANK = [
    ("tech", "backend", "mid", "谈谈你对高并发场景下缓存与数据库一致性的理解。", ["缓存", "一致性"]),
    ("tech", "backend", "mid", "如何设计一个高可用的分布式系统？请说明关键点。", ["高可用", "分布式"]),
    ("tech", "backend", "hard", "介绍一次你排查线上故障的完整过程。", ["故障排查"]),
    ("behavioral", "backend", "mid", "请用 STAR 法则介绍一个最有挑战的项目。", ["STAR"]),
    ("behavioral", "backend", "mid", "你如何评价自己的沟通与协作能力？请举例。", ["协作"]),
    ("case", "product", "mid", "如果让你负责一个新业务的冷启动，你会如何规划？", ["业务规划"]),
    ("hr", "backend", "mid", "你的期望薪资范围是多少？依据是什么？", ["薪资"]),
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 计划
        if db.query(Plan).count() == 0:
            for code, name, price, days, max_m, full, pdf, premium in PLANS:
                db.add(Plan(
                    code=code, name=name, price_cents=price, period_days=days,
                    max_interviews_month=max_m, full_report_enabled=full,
                    pdf_export_enabled=pdf, persona_premium=premium,
                ))
            print("[seed] plans 初始化完成")

        # 人设
        if db.query(InterviewerPersona).count() == 0:
            for p in PERSONAS:
                db.add(InterviewerPersona(**p))
            print("[seed] personas 初始化完成")

        # 题库
        if db.query(QuestionBank).count() == 0:
            for itype, cat, diff, text, tags in BANK:
                db.add(QuestionBank(
                    interview_type=itype, job_category=cat, difficulty=diff,
                    question_text=text, tags=tags,
                ))
            print("[seed] question_bank 初始化完成")

        db.commit()
        print("[seed] 完成")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
