from fastapi import APIRouter, Depends, HTTPException, status, Body, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import base64
import io
from PIL import Image
import numpy as np
import json
import logging

# 配置日誌
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from app.database import get_db, Employee
from app.schemas import EmployeeCreate, EmployeeUpdate, EmployeeResponse, StandardResponse, FaceRegistrationRequest
from app.auth import get_current_admin, get_password_hash
from app.api import auth
from models.face_recognition import register_face as face_model_register

router = APIRouter()

@router.get("/", response_model=List[EmployeeResponse])
async def get_all_employees(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(auth.get_current_active_user)
):
    """
    獲取所有員工 (僅管理員可用)
    """
    # 檢查是否為管理員
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權訪問此資源，需要管理員權限"
        )
    
    employees = db.query(Employee).offset(skip).limit(limit).all()
    return employees

@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(auth.get_current_active_user)
):
    """
    獲取指定員工信息 (僅管理員可用)
    """
    # 檢查權限 - 只能查看自己或管理員可以查看所有
    if current_user.id != employee_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權查看其他員工的資料"
        )
    
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到該員工"
        )
    return employee

@router.post("/", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    employee: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(auth.get_current_active_user)
):
    """
    創建新員工 (僅管理員可用)
    """
    # 檢查是否為管理員
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權創建員工，需要管理員權限"
        )
    
    # 檢查郵箱是否已存在
    db_employee = db.query(Employee).filter(Employee.email == employee.email).first()
    if db_employee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="郵箱已註冊"
        )
    
    # 創建新員工
    hashed_password = get_password_hash(employee.password)
    new_employee = Employee(
        name=employee.name,
        email=employee.email,
        hashed_password=hashed_password,
        is_admin=employee.is_admin
    )
    
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)
    
    return new_employee

@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: int,
    employee_data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(auth.get_current_active_user)
):
    """
    更新員工信息 (僅管理員可用)
    """
    # 檢查權限 - 只能更新自己或管理員可以更新所有
    if current_user.id != employee_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權更新其他員工的資料"
        )
    
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到該員工"
        )
    
    # 更新基本資料
    if employee_data.name is not None:
        employee.name = employee_data.name
    
    if employee_data.email is not None:
        # 檢查新郵箱是否已被使用
        if employee_data.email != employee.email:
            existing = db.query(Employee).filter(Employee.email == employee_data.email).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="該郵箱已被使用"
                )
        employee.email = employee_data.email
    
    if employee_data.password:
        employee.hashed_password = get_password_hash(employee_data.password)
    
    if employee_data.is_admin is not None:
        employee.is_admin = employee_data.is_admin
    
    db.commit()
    db.refresh(employee)
    
    return employee

@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(auth.get_current_active_user)
):
    """
    刪除員工 (僅管理員可用)
    """
    # 檢查是否為管理員
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權刪除員工，需要管理員權限"
        )
    
    # 保護默認管理員不被刪除
    if employee_id == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能刪除超級管理員賬戶"
        )
    
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到該員工"
        )
    
    db.delete(employee)
    db.commit()
    
    return None

@router.post("/register-face", status_code=status.HTTP_200_OK)
async def register_face_handler(
    request: FaceRegistrationRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(auth.get_current_active_user)
):
    """
    註冊或更新員工的人臉數據
    """
    # 檢查權限 - 只能為自己註冊人臉或管理員可以為所有人註冊
    if current_user.id != request.employee_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權為其他員工註冊人臉"
        )
    
    # 獲取員工
    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到該員工"
        )
    
    try:
        # 直接傳遞base64圖像數據
        result = face_model_register(request.employee_id, request.image)
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "無法從圖像中識別出人臉")
            )
        
        # 從models.face_recognition中獲取人臉編碼
        from models.face_recognition import known_faces
        import json
        
        # 獲取剛才註冊的人臉編碼
        face_encoding = known_faces.get(str(request.employee_id))
        if face_encoding:
            # 將人臉編碼保存到數據庫中
            employee.face_encoding = json.dumps(face_encoding)
            db.commit()
            db.refresh(employee)
        
        return {
            "success": True,
            "message": "人臉註冊成功"
        }
    except Exception as e:
        import traceback
        logger_error = traceback.format_exc()
        print(f"註冊人臉時出錯: {str(e)}\n{logger_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"註冊人臉時出錯: {str(e)}"
        )

@router.post("/test-face-recognition", status_code=status.HTTP_200_OK)
async def test_face_recognition(
    request: dict = Body(...),  # 預期包含 image 字段的 base64 圖像
    db: Session = Depends(get_db)
):
    """
    測試人臉識別功能，不需要身份驗證，僅用於調試
    """
    from models.face_recognition import recognize_face, detect_faces, load_faces_from_db
    import json
    import logging
    
    logger = logging.getLogger("test_face_recognition")
    
    try:
        # 從數據庫加載所有人臉編碼
        employees_with_face = db.query(Employee).filter(Employee.face_encoding.isnot(None)).all()
        
        # 轉換為人臉編碼字典
        face_encodings = {}
        for emp in employees_with_face:
            try:
                encoding = json.loads(emp.face_encoding)
                face_encodings[str(emp.id)] = encoding
            except:
                pass
        
        # 加載到人臉識別模塊
        if face_encodings:
            load_faces_from_db(face_encodings)
            logger.info(f"從數據庫加載了 {len(face_encodings)} 筆人臉數據")
        else:
            logger.warning("數據庫中沒有人臉數據")
        
        # 直接傳遞base64圖像
        image_data = request["image"]
        
        # 檢測是否有人臉
        # 先解碼base64為圖像
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        image_np = np.array(image)
        
        faces = detect_faces(image_np)
        has_face = len(faces) > 0
        
        if not has_face:
            return {
                "success": False,
                "message": "未檢測到人臉",
                "has_face": False
            }
        
        # 嘗試識別人臉
        employee_id = recognize_face(image_data, face_encodings)
        
        if not employee_id:
            return {
                "success": False,
                "message": "人臉檢測成功，但無法識別為已知人臉",
                "has_face": True,
                "recognized": False
            }
        
        # 獲取員工信息
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        
        return {
            "success": True,
            "message": f"成功識別為員工: {employee.name} (ID: {employee_id})",
            "has_face": True,
            "recognized": True,
            "employee_id": employee_id,
            "employee_name": employee.name
        }
    except Exception as e:
        import traceback
        logger_error = traceback.format_exc()
        print(f"測試人臉識別時出錯: {str(e)}\n{logger_error}")
        return {
            "success": False,
            "message": f"測試人臉識別時出錯: {str(e)}",
            "error": str(e)
        } 