# Railway部署指南

## 准备工作

1. 在Railway.com上注册账号并创建项目
2. 为项目添加PostgreSQL数据库服务

## 部署步骤

### 步骤1: 设置PostgreSQL数据库

1. 在Railway项目中，点击"+ New"按钮
2. 选择"Database"，然后选择"PostgreSQL"
3. 等待数据库创建完成
4. 点击数据库服务，查看"Connect"标签页获取数据库连接信息

### 步骤2: 部署后端服务

1. 在Railway项目中，点击"+ New"按钮
2. 选择"Deploy from GitHub repo"
3. 选择您的GitHub仓库
4. 设置以下环境变量:
   - `PORT`: 80
   - `SECRET_KEY`: 您的密钥（请使用强密码）
   - `DEFAULT_ADMIN_EMAIL`: 管理员邮箱
   - `DEFAULT_ADMIN_PASSWORD`: 管理员密码
   - `DEBUG`: False
   - `SECURE_COOKIES`: True

**注意**: Railway会自动为您提供`DATABASE_URL`环境变量，无需手动设置。

### 步骤3: 修改服务设置

1. 在部署的服务中，点击"Settings"
2. 设置构建命令为以下之一:
   - 标准Dockerfile: `docker build -t attendance-system .`
   - 专用Railway配置: `docker build -t attendance-system -f Dockerfile.railway .`
3. 设置启动命令为: `bash backend/scripts/start.sh`

## 故障排除

如果部署遇到问题，请检查以下几点:

1. **数据库连接问题**:
   - 确认Railway提供的`DATABASE_URL`环境变量格式正确
   - 查看应用日志中是否有数据库连接错误
   
2. **构建问题**:
   - 检查Docker构建日志
   - 确认所有依赖项都正确安装
   - 如果缺少模块，确认Dockerfile中安装了所有必要的Python包
   
3. **运行时错误**:
   - 查看应用日志
   - 确认`start.sh`脚本有执行权限
   - 检查常见错误消息如"ModuleNotFoundError"，这通常表示缺少依赖项

## 可用的服务URL

成功部署后，Railway会为您提供以下URL:
- 网站前端: `https://your-project-name.railway.app`
- API端点: `https://your-project-name.railway.app/api`
- 健康检查: `https://your-project-name.railway.app/health` 