import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# 开发环境未配置时，回退到本地 SQLite。
DEFAULT_DATABASE_URL = "sqlite:///./job_copilot.db"
DATABASE_URL = (os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL).strip() or DEFAULT_DATABASE_URL

# SQLite 需要 check_same_thread=False 才能在多线程（FastAPI）中共享连接；
# PostgreSQL 不需要此参数，传空 dict 即可。
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)


# 统一的声明式基类，确保所有 ORM 模型注册到同一份 metadata。
class Base(DeclarativeBase):
    pass


# FastAPI 依赖项：为每次请求提供 session，并在请求结束后确保释放。
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
