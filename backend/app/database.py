from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Date, ForeignKey, func, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
from datetime import datetime, date
from app.config import settings

# 取得資料庫連接 URL
DATABASE_URL = settings.complete_database_url
print(f"使用資料庫連接: {DATABASE_URL}")

# 建立 engine
engine = create_engine(DATABASE_URL)

# 建立 SessionLocal 類別
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 建立 Base 類別
Base = declarative_base()

# 資料庫依賴項
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 員工資料表
class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_admin = Column(Boolean, default=False)
    face_encoding = Column(Text, nullable=True)  # 存儲人臉編碼（JSON格式）
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 關聯到打卡記錄
    clock_records = relationship("ClockRecord", back_populates="employee")
    
    @property
    def has_face_encoding(self):
        """判斷是否已註冊人臉"""
        return self.face_encoding is not None and self.face_encoding.strip() != ""

# 打卡記錄資料表
class ClockRecord(Base):
    __tablename__ = "clock_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    date = Column(Date, default=date.today, index=True)  # 打卡日期
    clock_in = Column(DateTime, nullable=True)  # 上班打卡時間
    clock_out = Column(DateTime, nullable=True)  # 下班打卡時間
    with_mask = Column(Boolean, default=False)  # 是否戴口罩
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 關聯到員工
    employee = relationship("Employee", back_populates="clock_records") 