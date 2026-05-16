#!/bin/sh
set -e

# 确保数据目录存在且 appuser 有写权限
# Volume 首次挂载时可能由 root 创建，需要修正所有权
mkdir -p /app/data/uploads /app/data/resumes /app/data/chroma
chown -R appuser:appuser /app/data

# 切换到 appuser 执行实际命令
exec gosu appuser "$@"
