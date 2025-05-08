from fastapi import APIRouter, Depends, HTTPException, Body, status, Query, Path
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List, Optional
import base64
import io
from PIL import Image
import numpy as np
import json
import traceback
import logging

from app.database import ClockRecord, Employee, get_db
from app.schemas import ClockInRequest, ClockOutRequest, ClockRecordResponse, StatsResponse, DirectClockRequest, AttendanceNotification
from app.auth import get_current_employee, get_current_admin
from app.api import auth
from app.config import settings
from models.mask_detection import detect_mask
from models.face_recognition import recognize_face, detect_faces

# 避免循環導入
notify_attendance_func = None

# 設置日誌
logger = logging.getLogger(__name__)

router = APIRouter()

# 直接打卡 (無需登入驗證)
@router.post("/direct-clock", status_code=status.HTTP_201_CREATED)
async def direct_clock(
    request: DirectClockRequest,
    db: Session = Depends(get_db),
):
    """
    基於人臉辨識的直接打卡功能，無需登入
    任何人都可以通過攝像頭人臉識別進行打卡
    """
    try:
        # 記錄請求詳情以協助調試
        logger.info(f"收到直接打卡請求 - 圖像長度: {len(request.image) if request.image else 0}字節, 口罩狀態: {request.with_mask}")
        
        # 檢查圖像數據格式
        if not request.image:
            logger.error("無圖像數據")
            return {
                "success": False,
                "detail": "請提供有效的圖像數據"
            }
        
        # 解碼 base64 圖像
        try:
            image_bytes = base64.b64decode(request.image)
            logger.info(f"圖像解碼成功，大小: {len(image_bytes)}字節")
            image = Image.open(io.BytesIO(image_bytes))
            image_np = np.array(image)
            logger.info(f"圖像轉換為numpy數組成功，形狀: {image_np.shape}")
        except Exception as img_error:
            logger.error(f"圖像解碼或轉換失敗: {str(img_error)}")
            return {
                "success": False,
                "detail": "圖像數據格式錯誤，無法解碼"
            }
        
        # 先檢測圖像中是否包含人臉
        logger.info("開始檢測人臉...")
        face_detected = detect_faces(image_np)
        if face_detected:
            logger.info(f"檢測到人臉: {face_detected}")
        else:
            logger.warning("未在圖像中檢測到人臉")
            return {
                "success": False,
                "detail": "未在圖像中檢測到人臉，請確保面部清晰可見"
            }
        
        # 從數據庫加載所有人臉編碼數據
        try:
            logger.info("從數據庫加載所有人臉編碼數據...")
            # 查詢所有有人臉編碼的員工
            employees_with_face = db.query(Employee).filter(Employee.face_encoding.isnot(None)).all()
            
            # 轉換為人臉編碼字典
            face_encodings = {}
            for emp in employees_with_face:
                try:
                    encoding = json.loads(emp.face_encoding)
                    face_encodings[str(emp.id)] = encoding
                    logger.info(f"加載員工ID {emp.id} 的人臉編碼數據成功")
                except Exception as encoding_error:
                    logger.error(f"解析員工 {emp.id} 的人臉編碼失敗: {str(encoding_error)}")
                    continue
            
            logger.info(f"成功從數據庫加載 {len(face_encodings)} 筆人臉編碼數據")
            
            # 如果沒有人臉編碼數據，直接返回錯誤
            if not face_encodings:
                logger.warning("數據庫中沒有人臉編碼數據")
                return {
                    "success": False,
                    "detail": "系統中尚未註冊任何人臉資料，請先至「人臉註冊」頁面進行註冊"
                }
        except Exception as db_error:
            logger.error(f"從數據庫加載人臉編碼數據時出錯: {str(db_error)}")
            return {
                "success": False,
                "detail": "讀取人臉數據時出錯，請聯繫管理員"
            }
        
        # 嘗試識別人臉（將人臉編碼數據傳遞給識別函數）
        logger.info("開始識別人臉...")
        employee_id = recognize_face(image_np, face_encodings)
        
        # 如果無法識別人臉，返回明確的錯誤信息
        if not employee_id:
            logger.warning("無法識別人臉或該人臉未註冊")
            
            # 檢查是否有任何註冊的人臉數據
            face_count = db.query(Employee).filter(Employee.face_encoding.isnot(None)).count()
            logger.info(f"系統中已註冊的人臉數量: {face_count}")
            
            if face_count == 0:
                detail = "系統中尚未註冊任何人臉資料，請先至「人臉註冊」頁面進行註冊"
            else:
                detail = "無法識別您的人臉，請確保您已經註冊人臉數據並光線充足"
            
            return {
                "success": False,
                "detail": detail
            }
        
        # 查詢員工信息
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            logger.error(f"找不到員工信息 (ID: {employee_id})")
            return {
                "success": False,
                "detail": "找不到對應的員工信息，請聯繫管理員"
            }
        
        # 獲取今天的日期
        today = date.today()
        logger.info(f"嘗試為員工 {employee.name} (ID: {employee_id}) 打卡，日期: {today}")
        
        # 保存口罩狀態 - 使用前端傳來的數據或系統檢測結果
        has_mask = request.with_mask
        logger.info(f"前端傳來的口罩狀態: {'已佩戴' if has_mask else '未佩戴'}")
        
        # 可選：添加後端口罩檢測驗證（如果前端傳來已佩戴口罩的狀態）
        if has_mask:
            logger.info("驗證前端傳來的口罩狀態...")
            backend_mask_result = detect_mask(image_np)
            logger.info(f"後端口罩檢測結果: {'已佩戴' if backend_mask_result else '未佩戴'}")
            
            # 如果前端說有口罩但後端檢測沒有，記錄這個不一致
            if not backend_mask_result:
                logger.warning("前端與後端口罩檢測結果不一致！前端: 已佩戴, 後端: 未佩戴")
                # 可以選擇使用後端結果覆蓋前端結果
                # has_mask = backend_mask_result
        
        # 檢查今天是否已經有打卡記錄 - 使用安全的SQL查詢
        existing_record = db.query(ClockRecord).filter(
            ClockRecord.employee_id == employee_id,
            ClockRecord.date == today
        ).first()
        
        now = datetime.now()
        logger.info(f"當前時間: {now}")
        
        if not existing_record:
            # 創建新的上班打卡記錄
            try:
                logger.info("創建新的上班打卡記錄")
                new_record = ClockRecord(
                    employee_id=employee_id,
                    date=today,
                    clock_in=now,
                    with_mask=has_mask  # 確保使用with_mask字段
                )
                db.add(new_record)
                db.commit()
                db.refresh(new_record)
                logger.info(f"上班打卡成功 - 記錄ID: {new_record.id}, 員工: {employee.name}, 時間: {now}")
                
                # 異步通知
                if notify_attendance_func:
                    await notify_attendance_func(employee_id, f"{employee.name} 完成上班打卡")
                
                return {
                    "success": True,
                    "message": "上班打卡成功",
                    "employee_name": employee.name,
                    "timestamp": now.isoformat(),
                    "type": "clock_in"
                }
            except Exception as db_error:
                logger.error(f"數據庫提交上班打卡記錄時失敗: {str(db_error)}")
                db.rollback()
                return {
                    "success": False,
                    "detail": f"保存打卡記錄失敗，請稍後再試"
                }
        else:
            # 如果已經有上班記錄但沒有下班記錄，進行下班打卡
            if existing_record.clock_in and not existing_record.clock_out:
                try:
                    logger.info(f"更新下班打卡記錄，記錄ID: {existing_record.id}")
                    existing_record.clock_out = now
                    
                    # 更新口罩狀態（如果與上班時不同）
                    if existing_record.with_mask != has_mask:
                        logger.info(f"口罩狀態變化: 從 {'已佩戴' if existing_record.with_mask else '未佩戴'} 到 {'已佩戴' if has_mask else '未佩戴'}")
                    
                    # 更新with_mask字段
                    existing_record.with_mask = has_mask
                    
                    db.commit()
                    db.refresh(existing_record)
                    logger.info(f"下班打卡成功 - 記錄ID: {existing_record.id}, 員工: {employee.name}, 時間: {now}")
                    
                    # 異步通知
                    if notify_attendance_func:
                        await notify_attendance_func(employee_id, f"{employee.name} 完成下班打卡")
                    
                    return {
                        "success": True,
                        "message": "下班打卡成功",
                        "employee_name": employee.name,
                        "timestamp": now.isoformat(),
                        "type": "clock_out"
                    }
                except Exception as db_error:
                    logger.error(f"數據庫提交下班打卡記錄時失敗: {str(db_error)}")
                    db.rollback()
                    return {
                        "success": False,
                        "detail": f"保存打卡記錄失敗，請稍後再試"
                    }
            else:
                # 今天已經完成打卡，不需要再次打卡
                logger.info(f"員工 {employee.name} 今天已完成打卡，記錄ID: {existing_record.id}")
                return {
                    "success": True,
                    "message": "今天已完成打卡",
                    "employee_name": employee.name,
                    "timestamp": now.isoformat(),
                    "type": "completed"
                }
                
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"打卡錯誤詳情: {error_details}")
        
        # 返回對用戶友好的錯誤信息
        return {
            "success": False,
            "detail": f"打卡過程發生錯誤: {str(e)}"
        }

# 上班打卡 (使用登入驗證)
@router.post("/clock-in", status_code=status.HTTP_201_CREATED)
async def clock_in(
    request: ClockInRequest,
    db: Session = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    # 檢查是否為本人打卡或管理員操作
    if current_employee.id != request.employee_id and not current_employee.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權為其他員工打卡"
        )
    
    # 獲取目標員工
    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到該員工"
        )
    
    # 解碼 base64 圖像
    image_bytes = base64.b64decode(request.image)
    image = Image.open(io.BytesIO(image_bytes))
    image_np = np.array(image)
    
    # 從數據庫加載人臉編碼數據
    try:
        logger.info("從數據庫加載人臉編碼數據...")
        # 查詢所有有人臉編碼的員工
        employees_with_face = db.query(Employee).filter(Employee.face_encoding.isnot(None)).all()
        
        # 轉換為人臉編碼字典
        face_encodings = {}
        for emp in employees_with_face:
            try:
                encoding = json.loads(emp.face_encoding)
                face_encodings[str(emp.id)] = encoding
            except Exception as e:
                logger.error(f"解析員工 {emp.id} 的人臉編碼失敗: {str(e)}")
                continue
        
        logger.info(f"從數據庫加載了 {len(face_encodings)} 筆人臉編碼資料")
    except Exception as e:
        logger.error(f"加載人臉編碼數據失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="人臉資料載入失敗，請重試"
        )
    
    # 進行人臉辨識驗證 (傳入編碼資料)
    recognized_id = recognize_face(image_np, face_encodings)
    
    # 驗證人臉辨識結果，確保是本人打卡
    if recognized_id != request.employee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="人臉辨識失敗，無法驗證身份"
        )
    
    # 檢測是否有戴口罩
    has_mask = detect_mask(image_np) if request.has_mask else False
    
    # 獲取今天的日期
    today = date.today()
    
    # 檢查今天是否已經有打卡記錄
    existing_record = db.query(ClockRecord).filter(
        ClockRecord.employee_id == request.employee_id,
        ClockRecord.date == today
    ).first()
    
    if existing_record:
        if existing_record.clock_in:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="今天已經打過上班卡"
            )
    
    # 創建新記錄或更新現有記錄
    now = datetime.now()
    if not existing_record:
        new_record = ClockRecord(
            employee_id=request.employee_id,
            date=today,
            clock_in=now,
            with_mask=has_mask
        )
        db.add(new_record)
    else:
        existing_record.clock_in = now
        existing_record.with_mask = has_mask
    
    db.commit()
    
    # 異步通知
    if notify_attendance_func:
        await notify_attendance_func("clock_in", {
            "employee_id": request.employee_id,
            "employee_name": employee.name,
            "timestamp": now.isoformat(),
            "with_mask": has_mask
        })
    
    return {
        "success": True, 
        "message": "上班打卡成功",
        "timestamp": now.isoformat()
    }

# 下班打卡
@router.post("/clock-out", status_code=status.HTTP_200_OK)
async def clock_out(
    request: ClockOutRequest,
    db: Session = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    # 檢查是否為本人打卡或管理員操作
    if current_employee.id != request.employee_id and not current_employee.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權為其他員工打卡"
        )
    
    # 獲取目標員工
    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到該員工"
        )
    
    # 解碼 base64 圖像
    image_bytes = base64.b64decode(request.image)
    image = Image.open(io.BytesIO(image_bytes))
    image_np = np.array(image)
    
    # 從數據庫加載人臉編碼數據
    try:
        logger.info("從數據庫加載人臉編碼數據...")
        # 查詢所有有人臉編碼的員工
        employees_with_face = db.query(Employee).filter(Employee.face_encoding.isnot(None)).all()
        
        # 轉換為人臉編碼字典
        face_encodings = {}
        for emp in employees_with_face:
            try:
                encoding = json.loads(emp.face_encoding)
                face_encodings[str(emp.id)] = encoding
            except Exception as e:
                logger.error(f"解析員工 {emp.id} 的人臉編碼失敗: {str(e)}")
                continue
        
        logger.info(f"從數據庫加載了 {len(face_encodings)} 筆人臉編碼資料")
    except Exception as e:
        logger.error(f"加載人臉編碼數據失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="人臉資料載入失敗，請重試"
        )
    
    # 進行人臉辨識驗證 (傳入編碼資料)
    recognized_id = recognize_face(image_np, face_encodings)
    
    # 驗證人臉辨識結果，確保是本人打卡
    if recognized_id != request.employee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="人臉辨識失敗，無法驗證身份"
        )
    
    # 獲取今天的日期
    today = date.today()
    
    # 檢查今天是否有打卡記錄
    record = db.query(ClockRecord).filter(
        ClockRecord.employee_id == request.employee_id,
        ClockRecord.date == today
    ).first()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請先打上班卡"
        )
    
    if record.clock_out:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="今天已經打過下班卡"
        )
    
    # 更新下班打卡時間
    now = datetime.now()
    record.clock_out = now
    db.commit()
    
    # 異步通知
    if notify_attendance_func:
        await notify_attendance_func("clock_out", {
            "employee_id": request.employee_id,
            "employee_name": employee.name,
            "timestamp": now.isoformat()
        })
    
    return {
        "success": True, 
        "message": "下班打卡成功",
        "timestamp": now.isoformat()
    }

# 獲取特定員工的打卡記錄
@router.get("/employee/{employee_id}", response_model=List[ClockRecordResponse])
async def get_employee_records(
    employee_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    # 檢查權限，只能查看自己的記錄或管理員可以查看所有
    if current_employee.id != employee_id and not current_employee.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權查看其他員工的打卡記錄"
        )
    
    # 構建查詢
    query = db.query(ClockRecord).filter(ClockRecord.employee_id == employee_id)
    
    if start_date:
        query = query.filter(ClockRecord.date >= start_date)
    
    if end_date:
        query = query.filter(ClockRecord.date <= end_date)
    
    # 按日期降序排序
    records = query.order_by(ClockRecord.date.desc()).all()
    
    return records

# 獲取所有打卡記錄 (僅管理員)
@router.get("/all", response_model=List[ClockRecordResponse])
async def get_all_records(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user = Depends(auth.get_current_active_user),
):
    """
    獲取所有打卡記錄，需要管理員權限
    """
    # 檢查是否為管理員
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權訪問此資源，需要管理員權限"
        )
    
    try:
        # 構建查詢
        query = db.query(ClockRecord)
        
        # 應用日期過濾
        if start_date:
            query = query.filter(ClockRecord.date >= start_date)
        if end_date:
            query = query.filter(ClockRecord.date <= end_date)
        
        # 按日期和員工ID排序
        records = query.order_by(ClockRecord.date.desc(), ClockRecord.employee_id).all()
        
        return records
    except Exception as e:
        logger.error(f"獲取所有打卡記錄時出錯: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取數據失敗: {str(e)}"
        )

# 獲取打卡統計
@router.get("/statistics", response_model=StatsResponse)
async def get_statistics(
    date_param: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user = Depends(auth.get_current_active_user),
):
    """
    獲取打卡統計數據，需要管理員權限
    """
    # 檢查是否為管理員
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="無權訪問此資源，需要管理員權限"
        )
    
    try:
        # 使用指定日期或今天
        target_date = date_param or date.today()
        
        # 統計數據
        total_employees = db.query(Employee).count()
        
        # 今日打卡人數（有上班打卡記錄）
        clocked_in_count = db.query(ClockRecord).filter(
            ClockRecord.date == target_date,
            ClockRecord.clock_in.isnot(None)
        ).count()
        
        # The get down (已下班人數)
        clocked_out_count = db.query(ClockRecord).filter(
            ClockRecord.date == target_date,
            ClockRecord.clock_out.isnot(None)
        ).count()
        
        # 佩戴口罩打卡的人數
        with_mask_count = db.query(ClockRecord).filter(
            ClockRecord.date == target_date,
            ClockRecord.with_mask == True
        ).count()
        
        return {
            "total_employees": total_employees,
            "clocked_in": clocked_in_count,
            "clocked_out": clocked_out_count,
            "with_mask": with_mask_count,
            "date": target_date
        }
    except Exception as e:
        logger.error(f"獲取打卡統計時出錯: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取統計數據失敗: {str(e)}"
        )

# 設置通知函數
def set_notify_attendance_func(func):
    global notify_attendance_func
    notify_attendance_func = func 