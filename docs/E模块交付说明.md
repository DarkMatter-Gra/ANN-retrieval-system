# E 模块交付说明

## 1. 职责范围

E 模块对应“查询检索服务 + 测试文档演示”，核心责任包括：

- 单次 Top-K 查询检索
- `cell_id` 查询与原始向量查询
- 精确检索与 ANN 近似检索模式调度
- 元数据条件过滤
- 检索结果组织与元数据补全
- 批量检索任务与结果导出
- 查询结果可视化高亮点位服务
- 检索性能指标联通
- 测试脚本、测试用例和交付文档

## 2. 已完成代码

### 2.1 单次检索

文件：

- `backend/app/services/search_service.py`
- `backend/app/api/v1/search.py`
- `backend/app/schemas/search.py`

已完成能力：

- 支持 `query_type=cell_id`
- 支持 `query_type=vector`
- 支持 `mode=exact`
- 支持 `mode=ann`
- 支持 `top_k` 范围校验
- 支持查询向量维度校验
- 支持按索引 metric 计算距离：
  - `l2`
  - `ip`
  - `cosine`
- 返回字段：
  - `query_id`
  - `results`
  - `rank`
  - `cell_id`
  - `distance`
  - `score`
  - `cell_type`
  - `organ`
  - `sample_id`
  - `latency_ms`
  - `recall_estimate`
  - `mode_used`
  - `highlight_points`

### 2.2 条件过滤

已完成 `filters` 过滤逻辑，支持：

- `cell_type`
- `organ`
- `sample_id`
- `obs_ext` 里的扩展字段
- `obs_ext.xxx` 点号路径
- 单值过滤
- 多值列表过滤

实现策略：

- 无过滤时直接按目标索引检索。
- 有过滤时先拉取 ANN 候选，再按元数据过滤。
- 如果候选不足，自动回退到过滤子集上的精确检索，保证结果正确性。

说明：

- 该策略适合课程项目和演示，能保证返回结果满足过滤条件。
- 大规模生产系统可以继续升级为 bitmap 预过滤或按标签构建子索引。

### 2.3 批量检索

文件：

- `backend/app/tasks/batch_search_tasks.py`
- `backend/app/services/search_service.py`
- `backend/app/api/v1/tasks.py`

已完成能力：

- `POST /api/v1/batch-search`
- 批量任务落库
- 子查询逐条执行
- 任务进度更新
- JSONL 导出
- CSV 导出
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tasks/{task_id}/export`

### 2.4 导出文件下载

新增文件：

- `backend/app/api/v1/files.py`

新增接口：

- `GET /api/v1/files/exports/{filename}`

安全处理：

- 禁止路径穿越
- 校验导出文件存在
- 校验任务归属权限
- 非管理员只能下载自己的任务结果

### 2.5 可视化高亮

文件：

- `backend/app/services/visualization_service.py`
- `backend/app/api/v1/visualizations.py`

已完成能力：

- 支持文档路径：`GET /api/v1/visualizations/{query_id}/highlights`
- 兼容旧路径：`GET /api/v1/visualizations/highlights/{query_id}`
- 从进程内缓存读取最近查询高亮结果
- 缓存丢失时，从 `SearchTask.request_payload` 持久化记录回退读取

### 2.6 性能指标

文件：

- `backend/app/services/metrics_service.py`

单次检索现在会落 `SearchTask`，并记录：

- `latency_ms`
- `result_count`
- `mode_used`

因此 `/api/v1/metrics/search` 可以统计最近检索延迟。

### 2.7 本地任务模式

文件：

- `backend/app/core/config.py`
- `backend/app/tasks/celery_app.py`
- `backend/.env`

新增配置：

```env
CELERY_TASK_ALWAYS_EAGER=true
```

作用：

- 本机没有 Redis 时，Celery `delay()` 会在当前进程同步执行。
- 便于课程演示时先跑通上传、索引构建、批量检索和报告任务。
- 如果接入 Redis worker，将该值改为 `false`。

## 3. 联调账号和烟测数据

烟测脚本会创建：

```text
username: codex_smoke_user
password: SmokePass123
dataset_id: 运行时输出
index_id: 运行时输出
```

运行命令：

```bash
cd backend
python scripts/smoke_backend.py
```

脚本覆盖：

- 登录
- 单次 ANN 检索
- 条件过滤检索
- 批量检索
- 任务查询
- 结果导出下载
- 可视化高亮
- 指标查询
- 诊断报告

## 4. 正式测试

测试文件：

- `backend/tests/test_e_search_flow.py`

运行命令：

```bash
cd backend
python -m pytest
```

当前结果：

```text
6 passed, 1 warning
```

测试覆盖：

- 单次检索结果排序
- 条件过滤结果正确性
- 高亮结果持久化回退
- 批量检索任务完成
- CSV 导出下载
- metrics 联通
- API 创建索引
- `.index / .id_map.json / .meta.json` 产物生成
- 查询向量维度不匹配异常
- 诊断报告 JSON/PDF 生成与下载
- 导出/报告下载路径穿越与越权访问拦截

## 4.1 真实数据与性能补充测试

已补充老师提供的 `liver.h5ad` 真实数据测试：

- 细胞数：69032
- 基因数：32397
- PCA 向量维度：30
- 预处理、建索引、ANN 检索、精确检索、过滤检索、批量导出、指标、JSON/PDF 报告均通过

已补充 HNSW benchmark：

- Flat 精确检索作为 baseline
- 比较 HNSW `M / ef_construction / ef_search` 参数
- 输出 recall@10、平均延迟、p50、p95、p99、构建耗时
- 当前推荐参数：`M=32, ef_construction=200, ef_search=256`

## 5. 当前边界

已完成 E 模块代码和测试主体验收。

仍需与其他模块联调的内容：

- 真实 `.h5ad` 上传和预处理链路属于 C/B 主责，E 需要消费其入库结果。
- 前端图表交互属于 A 主责，E 已提供高亮和 embedding 接口。
- Redis + Celery worker 生产式异步部署属于 B/运维主责，E 已提供本地同步任务模式。
- 大规模 ANN 性能调参属于 D/E 交界，当前已完成统一 ANN 引擎升级，后续可继续做参数基准测试。
