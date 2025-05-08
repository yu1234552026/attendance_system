import sqlite3
import os
from datetime import date

def main():
    print("正在更新資料庫結構...")
    
    # 資料庫文件路徑
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "attendance.db")
    print(f"資料庫路徑: {db_path}")
    
    try:
        # 連接到資料庫
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 檢查 face_encoding 欄位是否存在於 employees 表
        cursor.execute("PRAGMA table_info(employees)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'face_encoding' not in column_names:
            print("添加 face_encoding 欄位到 employees 表...")
            cursor.execute("ALTER TABLE employees ADD COLUMN face_encoding TEXT")
            conn.commit()
            print("成功添加 face_encoding 欄位")
        else:
            print("face_encoding 欄位已存在")
        
        # 檢查 clock_records 表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clock_records'")
        if not cursor.fetchone():
            print("創建 clock_records 表...")
            cursor.execute("""
            CREATE TABLE clock_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                date TEXT,
                clock_in TIMESTAMP,
                clock_out TIMESTAMP,
                with_mask BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees (id)
            )
            """)
            conn.commit()
            print("成功創建 clock_records 表")
        else:
            # 檢查 date 欄位是否存在於 clock_records 表
            cursor.execute("PRAGMA table_info(clock_records)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'date' not in column_names:
                print("添加 date 欄位到 clock_records 表...")
                cursor.execute("ALTER TABLE clock_records ADD COLUMN date TEXT")
                conn.commit()
                print("成功添加 date 欄位")
                
                # 更新所有記錄，設置 date 欄位值為當前日期
                today = date.today().isoformat()
                cursor.execute("UPDATE clock_records SET date = ?", (today,))
                conn.commit()
                print(f"已將所有記錄的 date 欄位設為 {today}")
            else:
                print("date 欄位已存在")
                
            # 檢查 with_mask 欄位是否存在於 clock_records 表
            if 'with_mask' not in column_names:
                print("添加 with_mask 欄位到 clock_records 表...")
                cursor.execute("ALTER TABLE clock_records ADD COLUMN with_mask BOOLEAN DEFAULT 0")
                conn.commit()
                print("成功添加 with_mask 欄位")
            else:
                print("with_mask 欄位已存在")
        
        # 關閉連接
        conn.close()
        print("資料庫更新完成")
    except Exception as e:
        print(f"發生錯誤: {e}")

if __name__ == "__main__":
    main() 