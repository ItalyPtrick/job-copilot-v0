import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# 开发环境未配置时，回退到本地 SQLite。
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./job_copilot.db")

engine = create_engine(DATABASE_URL, echo=False)
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