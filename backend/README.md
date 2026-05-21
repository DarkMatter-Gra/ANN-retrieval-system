# ANN Retrieval Backend

FastAPI + SQLAlchemy + Celery + FAISS/HNSWLIB 后端实现。

## 快速开始

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 初始化数据库（首次）
alembic revision --autogenerate -m "init core tables"
alembic upgrade head

# 启动 API
uvicorn app.main:app --reload --port 8000

# 启动 Celery（另一个终端）
celery -A app.tasks.celery_app.celery_app worker --loglevel=INFO
```

## 目录结构

```
backend/
├── app/
│   ├── api/             # FastAPI 路由层
│   ├── core/            # 配置、安全、枚举、异常
│   ├── db/              # SQLAlchemy 基础
│   ├── models/          # ORM 模型
│   ├── schemas/         # Pydantic Schema
│   ├── services/        # 业务 Service
│   ├── tasks/           # Celery 任务
│   ├── utils/           # 工具函数
│   └── main.py          # FastAPI 入口
├── migrations/          # Alembic 迁移
├── alembic.ini
├── .env
├── requirements.txt
└── pyproject.toml
```

## 主要接口

- `/api/v1/auth/{register,login,me}`
- `/api/v1/users/{id}`（admin）
- `/api/v1/datasets/upload/{init,chunk,complete}`、`/api/v1/datasets/{id}`
- `/api/v1/indexes`、`/api/v1/indexes/{id}/{load,publish,rollback}`
- `/api/v1/search`、`/api/v1/batch-search`
- `/api/v1/tasks/{id}`
- `/api/v1/visualizations/{dataset_id}/embedding`
- `/api/v1/metrics/search`
- `/api/v1/reports/diagnostic`

## 统一响应

```json
{ "code": 0, "message": "ok", "data": {} }
```
