# 基础镜像使用Python 3.9
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    cmake \
    libopencv-dev \
    libsm6 \
    libxext6 \
    libxrender-dev \
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt
COPY backend/requirements.txt .

# 安装Python依赖
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn psycopg2-binary passlib[bcrypt]>=1.7.4 requests>=2.27.0

# 复制项目文件
COPY backend/ .

# 处理Render环境的配置
RUN if [ -f .env.render ]; then cp .env.render .env; fi
# 处理Railway环境的配置
RUN if [ -f .env.railway ]; then cp .env.railway .env; fi

# 运行脚本（用于初始化或迁移）
RUN chmod +x ./scripts/*.sh 2>/dev/null || true
RUN chmod +x ./scripts/*.py 2>/dev/null || true

# 创建必要的目录
RUN mkdir -p data static/css static/js templates

# 开放端口 - Render使用的是$PORT变量
EXPOSE $PORT

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# 启动应用 - 根据环境变量决定使用哪个启动脚本
CMD if [ -n "$RENDER" ]; then \
        sh ./scripts/render_start.sh; \
    elif [ -n "$RAILWAY_STATIC_URL" ]; then \
        sh ./scripts/start.sh; \
    else \
        uvicorn main:app --host 0.0.0.0 --port $PORT; \
    fi