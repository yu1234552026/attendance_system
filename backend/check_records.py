import sqlite3
import os
import logging
from datetime import datetime, date

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("check_records")

def check_database_records():
    """檢查資料庫中的打卡記錄"""
    try:
        # 確保我們在正確的目錄中
        db_path = 'attendance.db'
        if not os.path.exists(db_path):
            logger.error(f"數據庫文件 {db_path} 不存在")
            return False
            
        # 連接資料庫
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 檢查員工表
        cursor.execute("SELECT COUNT(*) FROM employees")
        employee_count = cursor.fetchone()[0]
        logger.info(f"員工數量: {employee_count}")
        
        # 顯示所有員工
        cursor.execute("SELECT id, name, email, is_admin FROM employees")
        employees = cursor.fetchall()
        for emp in employees:
            logger.info(f"員工ID: {emp[0]}, 姓名: {emp[1]}, Email: {emp[2]}, 管理員: {emp[3]}")
        
        # 檢查打卡記錄表
        try:
            cursor.execute("SELECT COUNT(*) FROM clock_records")
            record_count = cursor.fetchone()[0]
            logger.info(f"打卡記錄數量: {record_count}")
            
            # 檢查打卡記錄表結構
            cursor.execute("PRAGMA table_info(clock_records)")
            columns = cursor.fetchall()
            logger.info("打卡記錄表結構:")
            for col in columns:
                logger.info(f"  {col[1]} ({col[2]})")
            
            # 顯示所有打卡記錄
            cursor.execute("""
                SELECT cr.id, cr.employee_id, e.name, cr.date, 
                       cr.clock_in, cr.clock_out, cr.with_mask
                FROM clock_records cr
                LEFT JOIN employees e ON cr.employee_id = e.id
                ORDER BY cr.date DESC, cr.employee_id
            """)
            records = cursor.fetchall()
            
            if records:
                logger.info("打卡記錄列表:")
                for rec in records:
                    rec_id, emp_id, emp_name, rec_date, clock_in, clock_out, with_mask = rec
                    logger.info(f"記錄ID: {rec_id}, 員工: {emp_name}(ID:{emp_id}), 日期: {rec_date}, " +
                                f"上班: {clock_in}, 下班: {clock_out}, 口罩: {with_mask}")
            else:
                logger.warning("數據庫中沒有任何打卡記錄")
                
            # 檢查今天的打卡記錄
            today = date.today().isoformat()
            cursor.execute("""
                SELECT cr.id, cr.employee_id, e.name, cr.date, 
                       cr.clock_in, cr.clock_out, cr.with_mask
                FROM clock_records cr
                LEFT JOIN employees e ON cr.employee_id = e.id
                WHERE cr.date = ?
                ORDER BY cr.employee_id
            """, (today,))
            today_records = cursor.fetchall()
            
            if today_records:
                logger.info(f"今天({today})的打卡記錄:")
                for rec in today_records:
                    rec_id, emp_id, emp_name, rec_date, clock_in, clock_out, with_mask = rec
                    logger.info(f"記錄ID: {rec_id}, 員工: {emp_name}(ID:{emp_id}), " +
                                f"上班: {clock_in}, 下班: {clock_out}, 口罩: {with_mask}")
            else:
                logger.warning(f"今天({today})沒有任何打卡記錄")
                
        except sqlite3.OperationalError as e:
            logger.error(f"查詢打卡記錄時發生錯誤: {str(e)}")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"檢查數據庫記錄時發生錯誤: {str(e)}")
        return False

if __name__ == "__main__":
    check_database_records() 