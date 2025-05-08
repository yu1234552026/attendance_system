from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Header, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from datetime import timedelta
from app.database import get_db, Employee
from app.schemas import Token, LoginRequest, EmployeeCreate, StandardResponse, EmployeeResponse
from app.auth import (
    authenticate_employee, create_access_token,
    get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_employee
)

router = APIRouter()

# 修正 tokenUrl 為正確的路徑
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# 添加一個額外的依賴函數，可同時支持Cookie和Header中的token
def get_token_from_cookie_or_header(
    token: Optional[str] = Cookie(None, alias="access_token"), 
    authorization: Optional[str] = Header(None),
    request: Request = None
):
    # 優先從cookie獲取
    if token is not None:
        return token
    
    # 從Authorization頭部獲取
    if authorization is not None and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "")
    
    # 嘗試從請求查詢參數獲取
    if request is not None and 'token' in request.query_params:
        return request.query_params['token']
    
    # 如果都沒有，返回401錯誤
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未提供有效的認證信息",
        headers={"WWW-Authenticate": "Bearer"},
    )

# 修改以同時支持Cookie和Header認證
async def get_current_active_user(
    token: str = Depends(get_token_from_cookie_or_header), 
    db: Session = Depends(get_db)
):
    try:
        return await get_current_employee(token, db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"認證失敗: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    用戶登入並獲取 JWT token
    """
    employee = authenticate_employee(db, form_data.username, form_data.password)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用戶名或密碼錯誤",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(employee.id), "is_admin": employee.is_admin},
        expires_delta=access_token_expires
    )
    
    # 構建用戶信息對象
    user_data = {
        "id": employee.id,
        "name": employee.name,
        "email": employee.email,
        "is_admin": employee.is_admin
    }
    
    return {"access_token": access_token, "token_type": "bearer", "user": user_data}

@router.get("/me", response_model=dict)
async def get_current_user_info(current_employee: Employee = Depends(get_current_active_user)):
    """
    獲取當前登入用戶的信息
    """
    return {
        "id": current_employee.id,
        "name": current_employee.name,
        "email": current_employee.email,
        "is_admin": current_employee.is_admin
    }

@router.post("/register", response_model=EmployeeResponse)
async def register_user(user: EmployeeCreate, db: Session = Depends(get_db)):
    """
    註冊新員工（僅開發階段使用，生產環境應限制管理員訪問）
    """
    # 檢查郵箱是否已存在
    existing_user = db.query(Employee).filter(Employee.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="該郵箱已註冊"
        )
    
    # 創建新員工
    hashed_password = get_password_hash(user.password)
    new_employee = Employee(
        name=user.name,
        email=user.email,
        hashed_password=hashed_password,
        is_admin=user.is_admin  # 使用用戶提供的值
    )
    
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)
    
    return new_employee 