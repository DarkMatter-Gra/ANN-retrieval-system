# E 模块测试报告

## 1. 测试目标

验证 E 模块查询检索服务是否满足课程分工要求：

- 查询逻辑正确
- 条件过滤正确
- Top-K 结果组织正确
- 精确/近似模式可调度
- 批量检索任务可完成
- 检索结果可导出
- 可视化高亮接口可用
- 指标接口能读取检索延迟
- ANN 索引构建产物可追踪
- 异常请求能返回明确错误

## 2. 测试环境

后端目录：

```text
backend/
```

关键配置：

```env
DATABASE_URL=sqlite:///./ann_system.db
CELERY_TASK_ALWAYS_EAGER=true
```

说明：

- SQLite 用于本地课程联调。
- Celery eager 模式用于无 Redis 环境下同步执行异步任务。
- 接入 Redis worker 时可将 `CELERY_TASK_ALWAYS_EAGER` 改为 `false`。

## 3. 测试数据

测试脚本会自动创建小型数据集：

```text
dataset_name: codex_smoke_cells
cell_count: 6
feature_dim: 4
index_type: flat
metric: l2
```

测试细胞：

| cell_id | cell_type | organ | sample_id |
|---|---|---|---|
| cell_a | T_cell | blood | sample_1 |
| cell_b | T_cell | blood | sample_1 |
| cell_c | B_cell | blood | sample_2 |
| cell_d | Myeloid | lung | sample_3 |
| cell_e | Myeloid | lung | sample_3 |
| cell_f | NK_cell | blood | sample_4 |

## 4. 烟测命令

```bash
cd backend
python scripts/smoke_backend.py
```

成功输出示例：

```text
{
  "status": "ok",
  "username": "codex_smoke_user",
  "password": "SmokePass123",
  "dataset_id": 1,
  "index_id": 1,
  "query_id": "...",
  "batch_task_id": "..."
}
```

## 5. Pytest 测试命令

```bash
cd backend
python -m pytest
```

当前测试结果：

```text
6 passed, 1 warning
```

## 6. 测试用例

### TC-E-001 单次 ANN 检索

请求：

```json
{
  "dataset_id": 1,
  "index_id": 1,
  "query_type": "cell_id",
  "cell_id": "cell_a",
  "top_k": 3,
  "mode": "ann"
}
```

期望：

- HTTP 200
- 返回 `cell_a, cell_b, cell_c`
- 返回 `query_id`
- 返回 `latency_ms`
- 返回 `mode_used=ann`

### TC-E-002 条件过滤检索

请求：

```json
{
  "dataset_id": 1,
  "index_id": 1,
  "query_type": "cell_id",
  "cell_id": "cell_a",
  "top_k": 2,
  "mode": "ann",
  "filters": {
    "cell_type": ["Myeloid"]
  }
}
```

期望：

- HTTP 200
- 只返回 `cell_type=Myeloid` 的细胞
- 返回 `cell_d, cell_e`

### TC-E-003 高亮结果持久化回退

步骤：

1. 执行单次检索获得 `query_id`
2. 清空进程内 `_QUERY_CACHE`
3. 请求 `/api/v1/visualizations/{query_id}/highlights`

期望：

- 仍能从 `SearchTask.request_payload` 中恢复高亮结果
- 返回 query point 和 neighbor points

### TC-E-004 批量检索与导出下载

请求：

```json
{
  "dataset_id": 1,
  "index_id": 1,
  "top_k": 2,
  "mode": "ann",
  "queries": [
    {
      "query_type": "cell_id",
      "cell_id": "cell_a"
    },
    {
      "query_type": "cell_id",
      "cell_id": "cell_d",
      "filters": {
        "organ": "lung"
      }
    }
  ]
}
```

期望：

- 创建 batch task
- task 状态为 `done`
- `/tasks/{task_id}/export?format=csv` 返回下载 URL
- `/files/exports/{task_id}.csv` 可下载 CSV

### TC-E-005 API 创建索引并检查产物

请求：

```json
{
  "dataset_id": 1,
  "index_name": "pytest_flat_l2",
  "index_type": "flat",
  "metric": "l2",
  "params_json": {}
}
```

期望：

- task 状态为 `done`
- 生成 `.index`
- 生成 `.id_map.json`
- 生成 `.meta.json`
- meta 中 `vector_count=6`

### TC-E-006 查询向量维度错误

请求：

```json
{
  "dataset_id": 1,
  "index_id": 1,
  "query_type": "vector",
  "vector": [1.0, 2.0],
  "top_k": 3,
  "mode": "ann"
}
```

期望：

- HTTP 400
- 业务错误码 `40002`
- 错误信息提示维度不匹配

### TC-E-007 诊断报告 PDF 下载

步骤：

1. 执行单次检索获得 `query_id`
2. 请求 `POST /api/v1/reports/diagnostic`
3. 读取返回的 `download_url`
4. 请求 `/api/v1/files/reports/{filename}.pdf`

期望：

- HTTP 200
- 返回 PDF 文件
- 文件内容以 `%PDF` 开头
- 同时返回 JSON 报告下载地址

### TC-E-008 文件下载安全边界

步骤：

1. 请求 `/api/v1/files/exports/..%5Csecret.csv`
2. 请求 `/api/v1/files/reports/diagnostic.bad.exe`
3. 使用其他普通用户下载当前用户生成的 PDF 报告

期望：

- 路径穿越文件名返回 HTTP 400
- 不支持的报告扩展名返回 HTTP 400
- 非 owner 用户下载报告返回 HTTP 403
- 业务错误码分别为 `40002` 和 `40302`

## 7. 测试结论

E 模块已通过当前自动化测试：

- 单次检索可用
- 条件过滤可用
- 精确/近似调度可用
- 批量检索可用
- 导出下载可用
- 高亮结果可恢复
- 指标接口可读取延迟
- 索引产物完整
- 异常输入有明确错误
- 诊断报告 PDF 下载可用
- 文件下载路径和权限边界可控

真实数据补充测试已完成：

- 真实 `.h5ad` 数据端到端测试
- 大规模 Top-K 延迟测试
- HNSW recall@10 / latency benchmark

仍可继续扩展：

- IVF_PQ 召回率测试
- 并发查询压力测试
