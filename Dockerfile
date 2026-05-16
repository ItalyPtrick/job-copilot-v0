# ---- Stage 1: builder ----
# 用 uv 替代 pip：依赖解析快 10~50 倍，整体构建从 ~500s 降到 ~150s
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
# uv：Rust 写的 pip 替代品，下载 + 解析都极快
# --mount=type=cache：跨构建保留 uv 下载/构建缓存，减少重复下载
RUN --mount=type=cache,target=/root/.cache/uv \
    pip install --no-cache-dir uv && \
    uv pip install --system -r requirements.txt && \
    pip uninstall -y uv

# ---- Stage 2: runtime ----
# 最终镜像只含运行时，不包含 gcc / make / uv 等构建产物。
FROM python:3.11-slim

WORKDIR /app

# 从 builder 复制已安装的 Python 包，无需重新安装
COPY --from=builder /usr/local /usr/local

ENV PYTHONPATH=/app

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
