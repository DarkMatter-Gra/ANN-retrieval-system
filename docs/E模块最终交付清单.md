# E 模块最终交付清单

## 1. 交付范围

E 模块对应“查询检索服务 + 测试文档演示”，当前已完成以下能力：

- 单细胞 Top-K 检索
- `cell_id` 查询和原始向量查询
- ANN 近似检索和 Flat 精确检索
- `cell_type`、`organ`、`sample_id`、`obs_ext` 条件过滤
- 批量检索任务
- JSONL / CSV 结果导出
- 检索结果下载接口
- UMAP/t-SNE embedding 分页读取
- 检索结果高亮接口
- 检索性能指标接口
- JSON 诊断报告
- PDF 诊断报告
- 小数据自动化测试
- 老师真实 `liver.h5ad` 数据端到端测试
- HNSW 参数 recall/latency benchmark

## 2. 建议提交的代码文件

后端功能代码：

- `backend/app/services/search_service.py`
- `backend/app/services/ann_engine.py`
- `backend/app/services/preprocess_service.py`
- `backend/app/services/metrics_service.py`
- `backend/app/services/visualization_service.py`
- `backend/app/tasks/batch_search_tasks.py`
- `backend/app/tasks/report_tasks.py`
- `backend/app/api/v1/files.py`
- `backend/app/api/v1/reports.py`
- `backend/requirements.txt`
- `backend/pyproject.toml`
- `.gitignore`

测试和工具脚本：

- `backend/scripts/smoke_backend.py`
- `backend/scripts/real_liver_backend_test.py`
- `backend/scripts/benchmark_ann.py`
- `backend/tests/test_e_search_flow.py`

文档：

- `docs/E模块交付说明.md`
- `docs/E模块报告正文素材.md`
- `docs/E模块测试报告.md`
- `docs/真实数据测试报告.md`
- `docs/ANN引擎实现与升级说明.md`
- `docs/ANN性能基准测试报告.md`
- `docs/ANN_API_文档_工程内最新版.md`

## 3. 不建议提交的运行产物

以下内容是本地运行产物，不应进入 Git：

- `liver.h5ad`
- `backend/ann_system.db`
- `data/`
- `indices/`
- `exports/`
- `reports/`
- `*.log`
- `__pycache__/`
- `.pytest_cache/`

说明：`backend/ann_system.db` 当前因为真实数据测试被写入了 69032 条细胞向量和元数据，只适合本地演示，不适合作为仓库代码提交。

## 4. 复现命令

小数据 smoke 测试：

```powershell
cd backend
$env:PYTHONPATH='.'
python scripts\smoke_backend.py
```

自动化测试：

```powershell
cd backend
$env:PYTHONPATH='.'
pytest
```

真实数据端到端测试：

```powershell
cd backend
$env:PYTHONPATH='.'
python scripts\real_liver_backend_test.py ..\..\liver.h5ad
```

ANN benchmark：

```powershell
cd backend
$env:PYTHONPATH='.'
python scripts\benchmark_ann.py --dataset-id 1 --queries 200 --top-k 10
```

## 5. 当前验证结论

当前 E 模块已通过：

- `pytest`: 6 passed
- `smoke_backend.py`: status ok
- 真实 `liver.h5ad` 端到端测试：通过
- 真实数据 PDF 报告生成：通过
- ANN benchmark：通过

因此 E 模块代码和测试工作已经达到可交付状态。后续若继续加分，优先方向是扩展 benchmark 维度、优化过滤检索性能，以及把更多测试结果写入课程最终报告正文。
