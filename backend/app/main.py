"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import asr, auth, interviews, orders, positions, recycle_bin, reports, resumes, users

# 注册所有模型到 metadata（确保 create_all 建全表）
from app import models  # noqa: F401

app = FastAPI(
    title="AI 模拟面试助手 API",
    version="1.0.0",
    description="面霸 AI 后端服务：简历 × JD → 语音模拟面试 → 诊断报告",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_soft_delete_columns():
    """幂等迁移：为已有表补充回收站所需的 deleted_at 列（create_all 不会加列）"""
    from sqlalchemy import text
    from app.models.interview import InterviewSession
    from app.models.resume import Resume

    with engine.begin() as conn:
        for table in ("resumes", "interview_sessions"):
            exists = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    f"AND TABLE_NAME = '{table}' AND COLUMN_NAME = 'deleted_at'"
                )
            ).scalar()
            if not exists:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN deleted_at DATETIME NULL"))
                print(f"[迁移] {table} 已补充 deleted_at 列")


def _start_recycle_cleaner():
    """启动后台线程，每 6 小时自动清理回收站中超期（>7天）的数据"""
    import threading
    import time as _time

    from app.database import SessionLocal
    from app.services.recycle_service import purge_expired

    def _loop():
        while True:
            try:
                db = SessionLocal()
                try:
                    cleaned = purge_expired(db)
                    if cleaned:
                        print(f"[回收站] 已自动清理 {cleaned} 条超期数据")
                finally:
                    db.close()
            except Exception as exc:  # 清理失败不影响服务
                print(f"[回收站] 自动清理异常: {exc}")
            _time.sleep(6 * 3600)

    threading.Thread(target=_loop, daemon=True, name="recycle-cleaner").start()


@app.on_event("startup")
def on_startup():
    """启动时自动创建数据表（幂等，已存在的表会跳过）"""
    Base.metadata.create_all(bind=engine)
    _ensure_soft_delete_columns()
    _start_recycle_cleaner()
    # 打印外部服务配置状态，便于确认 .env 是否生效
    print("=" * 50)
    print("[启动检查] DeepSeek LLM 评分:", "已配置 ✓" if settings.DEEPSEEK_API_KEY else "未配置 ✗（将使用规则降级）")
    print("[启动检查] 百度 ASR 语音识别:", "已配置 ✓" if (settings.BAIDU_ASR_API_KEY and settings.BAIDU_ASR_SECRET_KEY) else "未配置 ✗（语音识别不可用）")
    from app.services.alipay_client import alipay_client
    print("[启动检查] 支付宝支付:", "已配置 ✓（" + ("沙箱" if "sandbox" in alipay_client.gateway else "生产") + "）" if alipay_client.is_configured() else "未配置 ✗（仅模拟收银台）")
    from app.services.email_client import email_client
    print("[启动检查] 邮箱验证码:", f"已配置 ✓（SMTP:{email_client.host}:{email_client.port}）" if email_client.is_configured() else "演示模式 ✗（验证码输出到后端日志）")
    print("=" * 50)
    # 历史数据修复：为已结束但缺少报告的会话补生成报告（幂等，无缺失时为空操作）
    from app.database import SessionLocal
    from app.services.report_engine import backfill_missing_reports
    db = SessionLocal()
    try:
        fixed = backfill_missing_reports(db)
        if fixed:
            print(f"[数据修复] 已为 {fixed} 场历史面试补生成诊断报告")
        # 为没有任何岗位的存量用户播种内置预设岗位（幂等）
        from app.services.preset_data import backfill_all_users
        seeded = backfill_all_users(db)
        if seeded:
            print(f"[数据修复] 已为存量用户播种 {seeded} 个预设岗位")
    finally:
        db.close()


@app.get("/api/health", tags=["健康检查"])
def health():
    return {"status": "ok", "service": "interview-ai"}


# 注册业务路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(resumes.router)
app.include_router(positions.router)
app.include_router(interviews.router)
app.include_router(reports.router)
app.include_router(recycle_bin.router)
app.include_router(asr.router)
app.include_router(orders.router)
