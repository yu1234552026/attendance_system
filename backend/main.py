from fastapi import FastAPI, Request, Depends, HTTPException, status, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import socketio
import logging
import os
from datetime import datetime, date, timedelta
from app.database import Base, engine, SessionLocal, Employee, ClockRecord, get_db
from app.api import auth, attendance, employee
from app.config import settings
from app.auth import get_password_hash, verify_password, create_access_token
from sqlalchemy.orm import Session

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main")

# 創建數據庫表
Base.metadata.create_all(bind=engine)

# 創建默認管理員賬戶（如果不存在）
def create_default_admin():
    try:
        db = SessionLocal()
        # 檢查是否已存在管理員
        admin = db.query(Employee).filter(Employee.email == settings.DEFAULT_ADMIN_EMAIL).first()
        if not admin:
            logger.info("創建默認管理員賬戶")
            hashed_password = get_password_hash(settings.DEFAULT_ADMIN_PASSWORD)
            # 確保郵箱格式符合標準
            admin_email = settings.DEFAULT_ADMIN_EMAIL
            if '@' in admin_email and '.' not in admin_email.split('@')[1]:
                admin_email = "admin@example.com"  # 使用標準格式的郵箱替代
            
            admin = Employee(
                name=settings.DEFAULT_ADMIN_NAME,
                email=admin_email,
                hashed_password=hashed_password,
                is_admin=True
            )
            db.add(admin)
            db.commit()
            logger.info(f"默認管理員已創建: {admin_email}, 密碼: {settings.DEFAULT_ADMIN_PASSWORD}")
        else:
            # 檢查並修復郵箱格式問題
            if '@' in admin.email and '.' not in admin.email.split('@')[1]:
                logger.info(f"修復管理員郵箱格式: {admin.email}")
                admin.email = "admin@example.com"
                db.commit()
                logger.info(f"管理員郵箱已更新為: admin@example.com")
            else:
                logger.info(f"默認管理員已存在: {admin.email}")
    except Exception as e:
        logger.error(f"創建管理員時發生錯誤: {str(e)}")
    finally:
        db.close()

# 執行初始化
create_default_admin()

# 建立 Socket.IO 伺服器
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio)

# 建立 FastAPI 應用
app = FastAPI(title="智能打卡系統", version="1.0.0")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 創建模板和靜態文件目錄
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
static_dir = os.path.join(os.path.dirname(__file__), "static")

# 確保目錄存在
os.makedirs(templates_dir, exist_ok=True)
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "css"), exist_ok=True)
os.makedirs(os.path.join(static_dir, "js"), exist_ok=True)

# 配置模板引擎
templates = Jinja2Templates(directory=templates_dir)

# 配置靜態文件
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 註冊 API 路由
app.include_router(auth.router, prefix="/api/auth", tags=["認證"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["打卡"])
app.include_router(employee.router, prefix="/api/employees", tags=["員工管理"])

# 將 Socket.IO 應用掛載到 FastAPI
app.mount("/socket.io", socket_app)

# Socket.IO 事件處理
@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")

# 打卡通知功能
async def notify_attendance(employee_id, message):
    await sio.emit('attendance_update', {
        'employee_id': employee_id,
        'message': message
    })

# 設置通知函數到 attendance 模塊
attendance.set_notify_attendance_func(notify_attendance)

# 獲取當前用戶
def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        logger.info("未檢測到 access_token cookie")
        return None
    
    try:
        from jose import jwt
        logger.info(f"嘗試解析 token: {token[:15]}...")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        id = payload.get("sub")
        is_admin_in_token = payload.get("is_admin", False)
        logger.info(f"Token 解析結果: user_id={id}, is_admin={is_admin_in_token}")
        
        if id is None:
            logger.warning("Token 不包含用戶 ID")
            return None
        
        # 使用id查詢用戶，而不是email
        user = db.query(Employee).filter(Employee.id == int(id)).first()
        if user:
            logger.info(f"成功找到用戶: id={user.id}, name={user.name}, is_admin={user.is_admin}")
        else:
            logger.warning(f"在資料庫中找不到 ID={id} 的用戶")
        return user
    except Exception as e:
        logger.error(f"解析token時出錯: {str(e)}")
        return None

# 驗證員工登入的功能
def authenticate_employee(db: Session, email: str, password: str):
    employee = db.query(Employee).filter(Employee.email == email).first()
    if not employee:
        return None
    if not verify_password(password, employee.hashed_password):
        return None
    return employee

# 主頁 - 直接顯示打卡界面
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse("attendance.html", {"request": request, "user": user})

# 登錄頁面
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        if user.is_admin:
            return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        else:
            return RedirectResponse(url="/attendance", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request})

# 登入處理
@app.post("/login")
async def login(
    request: Request, 
    response: Response,
    email: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    try:
        employee = authenticate_employee(db, email, password)
        if not employee:
            return templates.TemplateResponse(
                "login.html", 
                {"request": request, "error": "郵箱或密碼錯誤"},
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(employee.id), "is_admin": employee.is_admin},
            expires_delta=access_token_expires
        )
        
        # 修正 cookie 設置
        logger.info(f"設置 cookie，user: {employee.email}, is_admin: {employee.is_admin}")
        
        # 創建重定向響應
        if employee.is_admin:
            redirect_url = "/admin"
        else:
            redirect_url = "/attendance"
            
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
        
        # 在重定向響應上設置 cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax",  # 確保跨站點請求工作正常
            secure=False     # 本地開發用 False，生產環境應為 True
        )
        
        logger.info(f"登入成功，重定向到 {redirect_url}")
        return response
        
    except Exception as e:
        logger.error(f"登入過程中出錯: {str(e)}")
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "登入過程發生錯誤，請稍後再試"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# 打卡界面 - 無需登入，任何人都可以訪問
@app.get("/attendance", response_class=HTMLResponse)
async def attendance_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse("attendance.html", {"request": request, "user": user})

# 管理界面 - 需要管理員身份驗證
@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    logger.info(f"訪問管理員頁面，用戶: {user.name if user else 'None'}, 管理員: {user.is_admin if user else 'N/A'}")
    
    if not user:
        logger.warning("用戶未登入，重定向到登入頁面")
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    if not user.is_admin:
        logger.warning(f"用戶 {user.name} 不是管理員，重定向到首頁")
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    # 用戶是管理員，允許訪問
    logger.info(f"管理員 {user.name} 成功訪問管理頁面")
    return templates.TemplateResponse("admin.html", {"request": request, "user": user})

# 登出
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

# 人臉註冊頁面 - 需要登入權限
@app.get("/face-registration", response_class=HTMLResponse)
async def face_registration_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # 獲取員工列表 - 普通用戶只能看到自己，管理員可以看到所有員工
    if user.is_admin:
        employees = db.query(Employee).all()
    else:
        employees = [user]  # 普通用戶只能看到自己
    
    return templates.TemplateResponse(
        "face_registration.html", 
        {
            "request": request, 
            "user": user,
            "employees": employees
        }
    )

# API服務
@app.get("/api")
async def api_root():
    return {"message": "智能打卡系統 API 服務運行中"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=settings.DEBUG) 