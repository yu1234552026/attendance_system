#!/bin/bash

# 输出环境变量信息（排除敏感信息）
echo "启动环境: PORT=$PORT"
echo "数据库类型: $(echo $DATABASE_URL | cut -d':' -f1)"

# 如果是PostgreSQL数据库，初始化数据库
if [[ "$DATABASE_URL" == postgresql* ]]; then
  echo "初始化PostgreSQL数据库..."
  python scripts/init_postgres.py
fi

# 如果是从SQLite迁移到PostgreSQL
if [ -f "attendance.db" ] && [[ "$DATABASE_URL" == postgresql* ]]; then
  echo "检测到SQLite数据库文件和PostgreSQL环境，执行数据迁移..."
  python scripts/migrate_sqlite_to_postgres.py || echo "迁移脚本不存在或执行失败，跳过迁移"
fi

# 启动应用
echo "启动Web应用..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT 