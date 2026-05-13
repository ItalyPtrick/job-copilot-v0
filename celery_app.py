import os

from celery import Celery
from dotenv import load_dotenv

# Worker 独立进程启动，需自行加载环境变量
load_dotenv()

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")

celery = Celery("job_copilot", broker=CELERY_BROKER_URL)
celery.conf.update(
    result_backend=CELERY_BROKER_URL,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
)

# 自动发现 resume 模块中的 tasks
celery.autodiscover_tasks(["app.modules.resume"])
