# 智能考勤系統部署指南

## 方案一：使用Docker部署（推薦）

### 前置需求

- 安裝 [Docker](https://docs.docker.com/get-docker/)
- 安裝 [Docker Compose](https://docs.docker.com/compose/install/)

### 部署步驟

1. **克隆代碼倉庫**

```bash
git clone https://your-repository-url/attendance-system.git
cd attendance-system
```

2. **修改環境變數**

創建一個.env文件，並設置必要的環境變數：

```bash
cp .env.example .env
# 使用文本編輯器修改.env文件，設置安全的SECRET_KEY等
```

3. **啟動容器**

```bash
docker-compose up -d
```

4. **初始化資料庫（首次運行）**

```bash
docker-compose exec web python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

5. **訪問系統**

- 打卡頁面：http://your-domain.com/attendance
- 管理後台：http://your-domain.com/admin

### 日常維護

1. **查看日誌**

```bash
docker-compose logs -f web
```

2. **系統更新**

```bash
git pull
docker-compose up -d --build
```

3. **備份數據**

```bash
# PostgreSQL 備份
docker-compose exec db pg_dump -U postgres attendance > backup_$(date +%Y%m%d).sql
```

## 方案二：直接部署

### 前置需求

- Python 3.9+
- PostgreSQL數據庫（推薦）或SQLite
- Nginx（推薦）

### 部署步驟

1. **安裝系統依賴**

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3-dev build-essential cmake libopencv-dev
```

2. **安裝Python依賴**

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **設置環境變數**

```bash
export SECRET_KEY="your-secure-secret-key"
export DATABASE_URL="postgresql://user:password@localhost:5432/attendance"
export DEFAULT_ADMIN_EMAIL="admin@example.com"
export DEFAULT_ADMIN_PASSWORD="secure-admin-password"
```

4. **啟動應用**

```bash
cd backend
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

5. **設置Nginx**

創建 `/etc/nginx/sites-available/attendance.conf` 並連接到 `/etc/nginx/sites-enabled/`

6. **設置Systemd服務（可選）**

創建 `/etc/systemd/system/attendance.service` 文件：

```ini
[Unit]
Description=Attendance System
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/attendance-system/backend
Environment="PATH=/path/to/attendance-system/backend/venv/bin"
Environment="SECRET_KEY=your-secure-secret-key"
Environment="DATABASE_URL=postgresql://user:password@localhost:5432/attendance"
ExecStart=/path/to/attendance-system/backend/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000

[Install]
WantedBy=multi-user.target
```

啟動服務：

```bash
sudo systemctl enable attendance
sudo systemctl start attendance
```

## 常見問題解決

- **資料庫連接問題**：確保DATABASE_URL格式正確，並且資料庫服務已啟動
- **人臉識別失敗**：檢查OpenCV依賴是否正確安裝，可能需要重新編譯dlib
- **Socket.IO通訊問題**：確保Nginx配置中包含WebSocket支持

## 系統監控建議

- 使用Prometheus和Grafana監控系統性能
- 設置定期資料庫備份任務
- 設置日誌滾動，避免磁盤空間不足