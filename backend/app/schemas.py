from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date

# 通用響應模型
class StandardResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

# 用戶認證模型
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

# 員工模型
class EmployeeBase(BaseModel):
    name: str
    email: str  # 改為 str 以允許非標準郵箱格式
    is_admin: bool = False

class EmployeeCreate(EmployeeBase):
    password: str

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None  # 改為 str 以允許非標準郵箱格式
    password: Optional[str] = None
    is_admin: Optional[bool] = None

class EmployeeResponse(BaseModel):
    id: int
    name: str
    email: str  # 改為 str 以允許非標準郵箱格式
    is_admin: bool = False
    has_face_encoding: bool = False  # 添加表示是否已註冊人臉的字段
    created_at: datetime
    
    class Config:
        from_attributes = True

# 打卡請求模型
class ClockInRequest(BaseModel):
    employee_id: int
    image: str  # Base64 編碼的圖像
    has_mask: bool = False

class ClockOutRequest(BaseModel):
    employee_id: int
    image: str  # Base64 編碼的圖像

# 直接打卡請求模型 (無需登入)
class DirectClockRequest(BaseModel):
    image: str  # Base64 編碼的圖像
    with_mask: bool = False

# 打卡記錄響應模型
class ClockRecordResponse(BaseModel):
    id: int
    employee_id: int
    date: date
    clock_in: Optional[datetime] = None
    clock_out: Optional[datetime] = None
    with_mask: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True

# 統計數據響應模型
class StatsResponse(BaseModel):
    date: date
    total_employees: int
    clocked_in: int
    clocked_out: int
    with_mask: int

# 登入模型
class TokenData(BaseModel):
    id: int

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    is_admin: bool = False

class FaceRegistrationRequest(BaseModel):
    employee_id: int
    image: str  # base64 encoded image 

# 添加打卡通知模型
class AttendanceNotification(BaseModel):
    employee_id: int
    employee_name: Optional[str] = None
    timestamp: str
    with_mask: Optional[bool] = None
    message: Optional[str] = None
    type: Optional[str] = None  # clock_in, clock_out, completed 等 