FROM python:3.11-slim

WORKDIR /app

# 让 Python 能找到项目根目录下的 app 包（celery 不自动加当前目录到 sys.path）
ENV PYTHONPATH=/app

# 先装依赖 → 代码改动不触发重新 pip install（层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 非特权用户运行服务，避免容器内 root 权限
RUN mkdir -p /app/data/db && useradd --create-home appuser && chown -R appuser:appuser /app

# entrypoint 以 root 运行，修正 Volume 权限后切 appuser
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
