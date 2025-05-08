#!/bin/bash

echo "等待PostgreSQL数据库启动..."
sleep 5

echo "初始化PostgreSQL数据库..."
python scripts/init_postgres.py

echo "启动Web应用..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT 