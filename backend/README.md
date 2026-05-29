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

开发联调时如果本机没有 Redis，可以在 `.env` 中设置：

```env
CELERY_TASK_ALWAYS_EAGER=true
```

这样 `delay()` 会在当前 API 进程内同步执行，便于先跑通上传、建索引和批量检索链路。接入 Redis worker 时改回 `false`。

后端核心链路烟测：

```bash
python scripts/smoke_backend.py
```

该脚本会创建一个小型 `codex_smoke_cells` 数据集、Flat 索引和测试用户，并调用登录、单次检索、过滤检索、批量检索、可视化高亮、指标和诊断报告接口。

自动化测试：

```bash
python -m pytest
```

E 模块交付文档见：

- `../docs/E模块交付说明.md`
- `../docs/E模块测试报告.md`
- `../docs/ANN引擎实现与升级说明.md`

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
