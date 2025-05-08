import sqlite3
import os
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("update_db")

def update_db_structure():
    """更新數據庫結構，添加缺少的欄位"""
    try:
        # 確保我們在正確的目錄中
        db_path = 'attendance.db'
        if not os.path.exists(db_path):
            logger.error(f"數據庫文件 {db_path} 不存在")
            return False
            
        # 嘗試使用SQLite直接添加欄位
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 檢查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clock_records'")
        if not cursor.fetchone():
            logger.error("clock_records 表不存在")
            conn.close()
            return False
        
        # 檢查 updated_at 欄位是否存在
        cursor.execute("PRAGMA table_info(clock_records)")
        columns = [column[1] for column in cursor.fetchall()]
        logger.info(f"現有欄位: {columns}")
        
        if 'updated_at' not in columns:
            logger.info("正在添加 updated_at 欄位")
            cursor.execute("ALTER TABLE clock_records ADD COLUMN updated_at TIMESTAMP")
            conn.commit()
            logger.info("已成功添加 updated_at 欄位")
        else:
            logger.info("updated_at 欄位已存在")
            
        # 檢查 created_at 欄位是否存在
        if 'created_at' not in columns:
            logger.info("正在添加 created_at 欄位")
            cursor.execute("ALTER TABLE clock_records ADD COLUMN created_at TIMESTAMP")
            conn.commit()
            logger.info("已成功添加 created_at 欄位")
        else:
            logger.info("created_at 欄位已存在")
        
        conn.close()
        logger.info("數據庫結構更新完成")
        
        return True
    except Exception as e:
        logger.error(f"更新數據庫結構時發生錯誤: {str(e)}")
        return False

if __name__ == "__main__":
    update_db_structure() 