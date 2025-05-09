# 在生产环境中要修改的配置
import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API配置
    API_PREFIX: str = "/api"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # JWT密鑰和有效期
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-need-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    ALGORITHM: str = "HS256"
    
    # 資料庫配置
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    POSTGRES_USER: Optional[str] = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: Optional[str] = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB: Optional[str] = os.getenv("POSTGRES_DB")

    # 本地SQLite資料庫路徑 (當DATABASE_URL未設置時使用)
    @property
    def sqlite_db_path(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_dir = os.path.join(base_dir, "data")
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, "attendance.db")
    
    @property
    def complete_database_url(self) -> str:
        if self.DATABASE_URL:
            # 处理Railway提供的PostgreSQL URL (如果需要)
            db_url = self.DATABASE_URL
            if db_url.startswith("postgres://"):
                # Railway格式的URL: postgres://user:pass@host:port/db
                # 转换为SQLAlchemy格式: postgresql://user:pass@host:port/db
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            return db_url
        # 加上 check_same_thread=False 以支援多執行緒
        return f"sqlite:///{self.sqlite_db_path}?check_same_thread=False"
    
    # CORS設置
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # 默認管理員
    DEFAULT_ADMIN_EMAIL: str = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin")
    DEFAULT_ADMIN_NAME: str = os.getenv("DEFAULT_ADMIN_NAME", "系統管理員")
    
    # 圖片存儲
    MAX_IMAGE_SIZE: int = int(os.getenv("MAX_IMAGE_SIZE", str(10 * 1024 * 1024)))  # 10 MB
    
    # 生產環境設置
    SECURE_COOKIES: bool = os.getenv("SECURE_COOKIES", "False").lower() == "true"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # 允许未在模型中定义的环境变量

# 創建全局設置
settings = Settings()