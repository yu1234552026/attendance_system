#!/bin/bash

# 输出环境变量信息（排除敏感信息）
echo "启动环境: PORT=$PORT"
echo "数据库类型: $(echo $DATABASE_URL | cut -d':' -f1)"

# 初始化数据库
echo "初始化PostgreSQL数据库..."
python scripts/init_postgres.py

# 启动应用
echo "启动Web应用..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT 