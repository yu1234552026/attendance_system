import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
import time

# 添加父目录到系统路径，以便导入app模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import Base, Employee, ClockRecord
from app.auth import get_password_hash
from app.config import settings

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("init_postgres")

def main():
    # 获取数据库连接URL
    database_url = settings.complete_database_url
    if not database_url.startswith('postgresql'):
        logger.error(f"数据库URL不是PostgreSQL连接: {database_url}")
        logger.error("请检查环境变量DATABASE_URL是否正确设置")
        return
    
    logger.info(f"使用数据库连接类型: {database_url.split(':')[0]}")
    
    # 尝试连接数据库，最多重试5次
    max_retries = 5
    retry_count = 0
    while retry_count < max_retries:
        try:
            # 创建数据库引擎和连接
            engine = create_engine(database_url)
            engine.connect()  # 测试连接
            logger.info("数据库连接成功")
            break
        except Exception as e:
            retry_count += 1
            logger.warning(f"尝试 {retry_count}/{max_retries} 连接数据库失败: {str(e)}")
            if retry_count >= max_retries:
                logger.error("达到最大重试次数，无法连接数据库")
                raise
            time.sleep(5)  # 等待5秒后重试
    
    try:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # 创建所有表格
        logger.info("创建数据库表...")
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建完成")
        
        # 创建默认管理员账户
        db = SessionLocal()
        try:
            # 检查是否已存在管理员
            admin = db.query(Employee).filter(Employee.email == settings.DEFAULT_ADMIN_EMAIL).first()
            if not admin:
                logger.info("创建默认管理员账户")
                hashed_password = get_password_hash(settings.DEFAULT_ADMIN_PASSWORD)
                
                admin = Employee(
                    name=settings.DEFAULT_ADMIN_NAME,
                    email=settings.DEFAULT_ADMIN_EMAIL,
                    hashed_password=hashed_password,
                    is_admin=True
                )
                db.add(admin)
                db.commit()
                logger.info(f"默认管理员已创建: {settings.DEFAULT_ADMIN_EMAIL}")
            else:
                logger.info(f"默认管理员已存在: {settings.DEFAULT_ADMIN_EMAIL}")
        finally:
            db.close()
            
        logger.info("PostgreSQL数据库初始化完成")
    except Exception as e:
        logger.error(f"初始化数据库时发生错误: {str(e)}")
        raise

if __name__ == "__main__":
    main() 