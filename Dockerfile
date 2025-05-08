# 基础镜像使用Python 3.9
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=80

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libopencv-dev \
    libsm6 \
    libxext6 \
    libxrender-dev \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt
COPY backend/requirements.txt .

# 安装Python依赖
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir passlib[bcrypt]>=1.7.4 requests>=2.27.0

# 复制项目文件
COPY backend/ .

# 运行脚本（用于初始化或迁移）
RUN chmod +x ./scripts/*.sh 2>/dev/null || true

# 开放端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# 启动应用
CMD ["sh", "./scripts/start.sh"]