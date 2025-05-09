# Render部署指南

## 前提条件

1. 拥有GitHub账户并将代码推送到GitHub仓库
2. 注册Render账户 (https://render.com)

## 部署步骤

### 方法一：使用Blueprint（推荐）

1. 登录到Render并点击"New +"
2. 选择"Blueprint"
3. 连接您的GitHub仓库
4. 授权Render访问您的仓库
5. 选择包含`render.yaml`文件的仓库
6. 点击"Apply Blueprint"，Render将自动设置所有服务

### 方法二：手动设置

#### 1. 创建PostgreSQL数据库

1. 在Render控制台中点击"New +"
2. 选择"PostgreSQL"
3. 填写数据库信息：
   - 名称：`attendance-db`
   - 选择区域（建议选择离您用户最近的区域）
   - 选择计划（Free计划足够测试使用）
4. 点击"Create Database"
5. 等待数据库创建完成，并保存数据库的"Internal Database URL"

#### 2. 部署Web服务

1. 在Render控制台中点击"New +"
2. 选择"Web Service"
3. 连接您的GitHub仓库
4. 填写服务信息：
   - 名称：`attendance-system`
   - 区域：选择与数据库相同的区域
   - 环境：Docker
   - 分支：`main`（或您的主分支）
   - 计划：Free
5. 点击"Advanced"设置以下环境变量：
   - `DATABASE_URL`：使用上一步获取的数据库URL
   - `SECRET_KEY`：设置一个随机字符串作为密钥
   - `DEBUG`：`false`
   - `SECURE_COOKIES`：`true`
   - `ACCESS_TOKEN_EXPIRE_MINUTES`：`480`
   - `DEFAULT_ADMIN_EMAIL`：设置管理员邮箱
   - `DEFAULT_ADMIN_PASSWORD`：设置管理员密码（部署后记得修改）
   - `DEFAULT_ADMIN_NAME`：设置管理员名称
   - `RENDER`：`true`（告诉应用它运行在Render环境）
6. 点击"Create Web Service"

## 数据迁移

如果您的应用程序之前使用SQLite数据库并且已有数据，系统将自动执行以下操作：

1. 检测到SQLite数据库文件`attendance.db`
2. 运行迁移脚本`migrate_sqlite_to_postgres.py`
3. 将SQLite中的所有数据（员工和打卡记录）迁移到PostgreSQL

迁移过程会在首次部署时自动执行，您只需确保将SQLite数据库文件一起推送到GitHub仓库。

## 常见问题解决

1. **无法连接数据库**：
   - 检查`DATABASE_URL`环境变量是否正确设置
   - 确保您的服务器IP被添加到数据库的允许列表中

2. **部署失败**：
   - 查看Render的部署日志以获取详细错误信息
   - 检查Dockerfile是否有语法错误

3. **首次登录失败**：
   - 确保管理员账户创建成功（检查日志）
   - 确认您使用的是正确的管理员邮箱和密码

4. **静态资源不加载**：
   - 检查您的应用中静态文件路径是否正确配置
   - 确保静态文件已正确复制到Docker镜像中

## 访问您的应用

成功部署后，您可以通过以下URL访问您的应用：
- 主页：`https://attendance-system.onrender.com`
- API：`https://attendance-system.onrender.com/api`
- 健康检查：`https://attendance-system.onrender.com/health`

## 维护

- 每次您推送更改到GitHub仓库主分支时，Render将自动重新部署您的应用
- Render Free计划的PostgreSQL数据库会在90天不活动后被删除，请确保保持活跃使用或定期备份数据 