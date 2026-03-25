# 情绪管理与智能坐垫干预系统 - 后端服务

## 项目简介

这是一个软硬件结合的健康管理系统后端服务。智能坐垫硬件（点点甜睡品牌）采集用户心率、呼吸等生理数据，通过厂家云服务API提供数据接口。本系统负责：

- 对接厂家云服务API拉取数据
- 接收厂家Webhook推送的实时数据和报告
- 用模拟算法计算HRV、压力指数等高级指标
- 调用AI大模型生成健康报告
- 为H5前端和SaaS后台提供REST API

## 技术栈

- **Python 3.11+**
- **FastAPI** - 异步Web框架
- **SQLAlchemy 2.0** - ORM（async，使用 mapped_column 新语法）
- **PostgreSQL** - 主数据库
- **Redis** - 缓存和消息队列
- **Alembic** - 数据库迁移
- **Pydantic V2** - 数据校验
- **httpx** - 异步HTTP客户端
- **uvicorn** - ASGI服务器

## 项目结构

```
backend/
├── alembic/                    # 数据库迁移
│   ├── versions/               # 迁移版本文件
│   ├── env.py                  # Alembic环境配置
│   └── script.py.mako          # 迁移脚本模板
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI入口
│   ├── config.py               # 配置管理
│   ├── database.py             # 数据库连接
│   ├── models/                 # SQLAlchemy ORM模型
│   │   ├── __init__.py
│   │   ├── tenant.py           # 租户模型
│   │   ├── user.py             # 用户模型
│   │   ├── device.py           # 设备模型
│   │   └── measurement.py      # 检测记录模型
│   ├── schemas/                # Pydantic模型
│   │   ├── __init__.py
│   │   ├── tenant.py
│   │   ├── user.py
│   │   ├── device.py
│   │   └── measurement.py
│   ├── api/                    # API路由
│   │   ├── __init__.py
│   │   ├── router.py           # 总路由注册
│   │   ├── tenants.py
│   │   ├── users.py
│   │   ├── devices.py
│   │   └── measurements.py
│   ├── services/               # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── cushion_cloud_client.py  # 厂家API客户端
│   │   └── device_service.py
│   └── utils/                  # 工具函数
│       ├── __init__.py
│       └── security.py
├── .env.example                # 环境变量模板
├── .env                        # 环境变量配置
├── requirements.txt            # Python依赖
├── alembic.ini                 # Alembic配置
└── README.md                   # 项目文档
```

## 快速开始

### 1. 环境准备

确保已安装：
- Python 3.11+
- PostgreSQL 14+
- Redis 6+

### 2. 安装依赖

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入实际配置
```

主要配置项：
```env
# 数据库连接
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/emotion_cushion

# Redis连接
REDIS_URL=redis://localhost:6379/0

# 点点甜睡云服务
CUSHION_CLOUD_USERNAME=your_username
CUSHION_CLOUD_PASSWORD=your_password

# AI大模型
SILICONFLOW_API_KEY=your_api_key
```

### 4. 创建数据库

```bash
# PostgreSQL
createdb emotion_cushion
# 或使用 psql
psql -U postgres -c "CREATE DATABASE emotion_cushion;"
```

### 5. 运行数据库迁移

```bash
# 生成迁移文件（如果有模型变更）
alembic revision --autogenerate -m "描述信息"

# 执行迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 6. 启动服务

```bash
# 开发模式（热重载）
python -m app.main

# 或使用 uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 7. 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## API 接口

### 统一响应格式

```json
{
  "code": 200,
  "msg": "success",
  "data": { ... }
}
```

### 接口列表

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| **租户** | POST | /api/v1/tenants | 创建租户 |
| | GET | /api/v1/tenants | 租户列表(分页) |
| | GET | /api/v1/tenants/{id} | 租户详情 |
| | PUT | /api/v1/tenants/{id} | 更新租户 |
| | DELETE | /api/v1/tenants/{id} | 删除租户 |
| **用户** | POST | /api/v1/users | 创建用户 |
| | GET | /api/v1/users | 用户列表(支持租户过滤) |
| | GET | /api/v1/users/{id} | 用户详情 |
| | PUT | /api/v1/users/{id} | 更新用户 |
| | DELETE | /api/v1/users/{id} | 删除用户 |
| **设备** | POST | /api/v1/devices | 创建设备 |
| | GET | /api/v1/devices | 设备列表(支持租户/状态过滤) |
| | GET | /api/v1/devices/{id} | 设备详情 |
| | PUT | /api/v1/devices/{id} | 更新设备 |
| | DELETE | /api/v1/devices/{id} | 删除设备 |
| | POST | /api/v1/devices/{id}/sync | 同步设备状态 |
| **检测记录** | POST | /api/v1/measurements | 创建记录 |
| | GET | /api/v1/measurements | 记录列表(支持用户/设备过滤) |
| | GET | /api/v1/measurements/{id} | 记录详情 |
| | PUT | /api/v1/measurements/{id} | 更新记录 |
| | DELETE | /api/v1/measurements/{id} | 删除记录 |
| | POST | /api/v1/measurements/{id}/analyze | 触发AI分析 |

### 健康检查

```
GET /health
```

返回：
```json
{
  "code": 200,
  "msg": "healthy",
  "data": {
    "app_name": "情绪管理与智能坐垫干预系统",
    "version": "1.0.0",
    "status": "running"
  }
}
```

## 数据模型

### 租户 (Tenant)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | String(100) | 商家名称 |
| type | String(50) | 商家类型: chinese_medicine/hotel/wellness_center |
| contact_phone | String(20) | 联系电话 |
| address | String(500) | 地址 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 用户 (User)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| tenant_id | UUID | 所属租户ID |
| name | String(50) | 用户姓名 |
| gender | String(10) | 性别: male/female/other |
| age | Integer | 年龄 |
| height | Float | 身高(cm) |
| weight | Float | 体重(kg) |
| bmi | Float | BMI(自动计算) |
| phone | String(20) | 联系电话 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 设备 (Device)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| device_code | String(50) | 设备编码(SN号)，唯一 |
| tenant_id | UUID | 所属租户ID |
| status | String(20) | 设备状态: online/offline/in_use |
| device_type | String(100) | 设备型号 |
| ble_mac | String(20) | 蓝牙MAC |
| wifi_mac | String(20) | WiFi MAC |
| firmware_version | String(20) | 固件版本 |
| hardware_version | String(20) | 硬件版本 |
| cloud_device_id | Integer | 厂家云平台设备ID |
| last_online_at | DateTime | 最后在线时间 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 检测记录 (MeasurementRecord)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 用户ID |
| device_id | UUID | 设备ID |
| start_time | DateTime | 检测开始时间 |
| end_time | DateTime | 检测结束时间 |
| duration_minutes | Integer | 检测时长(分钟) |
| status | String(20) | 状态: measuring/processing/completed/failed |
| raw_data_summary | JSON | 原始数据摘要 |
| derived_metrics | JSON | 衍生指标(HRV、压力指数等) |
| ai_analysis | Text | AI分析报告(Markdown) |
| health_score | Integer | 健康评分(0-100) |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

## 点点甜睡云服务对接

### API客户端使用

```python
from app.services.cushion_cloud_client import CushionCloudClient

async with CushionCloudClient() as client:
    # 获取设备信息
    device_info = await client.get_device_list("TA0096400014")
    
    # 获取睡眠数据
    data = await client.get_device_data(
        device_code="TA0096400014",
        start_time="2024-01-01 00:00:00",
        end_time="2024-01-01 08:00:00"
    )
    
    # 获取报告列表
    reports = await client.get_report_list("TA0096400014")
```

### Webhook验证

```python
from app.services.cushion_cloud_client import CushionCloudClient

# 验证签名
is_valid = CushionCloudClient.verify_webhook_signature(
    payload=request_body,
    signature=request.headers.get("X-Signature"),
    secret=settings.CUSHION_CLOUD_WEBHOOK_SECRET
)

# 解析数据
data = CushionCloudClient.parse_webhook_data(request_json)
```

## 开发指南

### 代码风格

```bash
# 格式化代码
black app/

# 排序导入
isort app/
```

### 运行测试

```bash
pytest tests/ -v
```

### 数据库迁移

```bash
# 创建新的迁移文件
alembic revision --autogenerate -m "添加新字段"

# 执行迁移
alembic upgrade head

# 回滚一个版本
alembic downgrade -1

# 查看迁移历史
alembic history
```

## 生产部署

### 使用Gunicorn + Uvicorn

```bash
gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --keep-alive 5
```

### Docker部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 环境变量清单

| 变量名 | 必填 | 说明 |
|--------|------|------|
| DATABASE_URL | 是 | PostgreSQL连接URL |
| REDIS_URL | 是 | Redis连接URL |
| CUSHION_CLOUD_USERNAME | 是 | 点点甜睡账号 |
| CUSHION_CLOUD_PASSWORD | 是 | 点点甜睡密码 |
| CUSHION_CLOUD_WEBHOOK_SECRET | 否 | Webhook签名密钥 |
| SILICONFLOW_API_KEY | 否 | AI大模型API密钥 |
| DEBUG | 否 | 调试模式，默认false |

## License

MIT
