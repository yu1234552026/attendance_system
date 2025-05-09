#!/usr/bin/env python
import os
import sys
import logging
import json
import sqlite3
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 添加父目录到系统路径，以便导入app模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import Base, Employee, ClockRecord
from app.config import settings

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("migrate_sqlite_to_postgres")

def date_converter(value):
    """将字符串转换为日期对象"""
    if value:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except:
            return None
    return None

def datetime_converter(value):
    """将字符串转换为日期时间对象"""
    if value:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
        except:
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except:
                return None
    return None

def bool_converter(value):
    """将整数转换为布尔值"""
    if value is not None:
        return bool(value)
    return False

def migrate_employees(sqlite_conn, postgres_session):
    """迁移员工数据"""
    logger.info("开始迁移员工数据...")
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT id, name, email, hashed_password, is_admin, face_encoding, created_at, updated_at FROM employees")
    rows = cursor.fetchall()
    
    for row in rows:
        id, name, email, hashed_password, is_admin, face_encoding, created_at, updated_at = row
        
        # 检查用户是否已存在
        existing_employee = postgres_session.query(Employee).filter(Employee.id == id).first()
        if existing_employee:
            logger.info(f"员工 ID {id} 已存在，跳过...")
            continue
            
        employee = Employee(
            id=id,
            name=name,
            email=email,
            hashed_password=hashed_password,
            is_admin=bool_converter(is_admin),
            face_encoding=face_encoding,
            created_at=datetime_converter(created_at),
            updated_at=datetime_converter(updated_at)
        )
        postgres_session.add(employee)
    
    postgres_session.commit()
    logger.info(f"成功迁移 {len(rows)} 条员工数据")

def migrate_clock_records(sqlite_conn, postgres_session):
    """迁移打卡记录数据"""
    logger.info("开始迁移打卡记录...")
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT id, employee_id, date, clock_in, clock_out, with_mask, created_at, updated_at FROM clock_records")
    rows = cursor.fetchall()
    
    for row in rows:
        id, employee_id, date_str, clock_in, clock_out, with_mask, created_at, updated_at = row
        
        # 检查记录是否已存在
        existing_record = postgres_session.query(ClockRecord).filter(ClockRecord.id == id).first()
        if existing_record:
            logger.info(f"打卡记录 ID {id} 已存在，跳过...")
            continue
            
        record = ClockRecord(
            id=id,
            employee_id=employee_id,
            date=date_converter(date_str),
            clock_in=datetime_converter(clock_in),
            clock_out=datetime_converter(clock_out),
            with_mask=bool_converter(with_mask),
            created_at=datetime_converter(created_at),
            updated_at=datetime_converter(updated_at)
        )
        postgres_session.add(record)
    
    postgres_session.commit()
    logger.info(f"成功迁移 {len(rows)} 条打卡记录")

def main():
    # 获取 SQLite 数据库路径
    sqlite_path = settings.sqlite_db_path  # 使用配置中的 SQLite 路径
    if not os.path.exists(sqlite_path):
        logger.error(f"SQLite 数据库文件不存在: {sqlite_path}")
        return
    
    # 获取 PostgreSQL 连接 URL
    postgres_url = settings.complete_database_url
    if not postgres_url.startswith('postgresql'):
        logger.error(f"数据库 URL 不是 PostgreSQL 连接: {postgres_url}")
        return
    
    try:
        # 连接到 SQLite 数据库
        logger.info(f"连接 SQLite 数据库: {sqlite_path}")
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        
        # 连接到 PostgreSQL 数据库
        logger.info(f"连接 PostgreSQL 数据库: {postgres_url.split('@')[1] if '@' in postgres_url else 'hidden'}")
        engine = create_engine(postgres_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        postgres_session = SessionLocal()
        
        # 创建数据库表（如果不存在）
        Base.metadata.create_all(bind=engine)
        
        # 执行数据迁移
        migrate_employees(sqlite_conn, postgres_session)
        migrate_clock_records(sqlite_conn, postgres_session)
        
        logger.info("数据迁移完成！")
    except Exception as e:
        logger.error(f"迁移过程中发生错误: {str(e)}")
        raise
    finally:
        # 关闭连接
        if 'sqlite_conn' in locals():
            sqlite_conn.close()
        if 'postgres_session' in locals():
            postgres_session.close()

if __name__ == "__main__":
    main() 