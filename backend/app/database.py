"""数据库引擎与会话管理"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# pool_pre_ping 保证连接失效自动重连；pool_recycle 避免 MySQL wait_timeout 断连
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI 依赖：为每个请求提供独立会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
