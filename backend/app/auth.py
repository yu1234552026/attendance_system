from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import TokenData
from app.database import Employee
from app.config import settings

# 密碼上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 密碼流 - 修正路徑
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# 驗證密碼
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# 生成密碼哈希
def get_password_hash(password):
    return pwd_context.hash(password)

# 獲取用戶
def get_employee(db: Session, email: str):
    return db.query(Employee).filter(Employee.email == email).first()

# 驗證用戶
def authenticate_employee(db: Session, email: str, password: str):
    employee = get_employee(db, email)
    if not employee:
        return False
    if not verify_password(password, employee.hashed_password):
        return False
    return employee

# 創建訪問令牌
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# 獲取當前用戶
async def get_current_employee(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無效的身份驗證憑證",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        id: int = payload.get("sub")
        if id is None:
            raise credentials_exception
        token_data = TokenData(id=id)
    except JWTError:
        raise credentials_exception
    
    employee = db.query(Employee).filter(Employee.id == token_data.id).first()
    if employee is None:
        raise credentials_exception
    return employee

# 檢查是否為管理員
async def get_current_admin(current_employee: Employee = Depends(get_current_employee)):
    if not current_employee.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="權限不足，需要管理員權限"
        )
    return current_employee 

ACCESS_TOKEN_EXPIRE_MINUTES=60 * 8