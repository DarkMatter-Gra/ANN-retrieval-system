# ANN 引擎实现与升级说明

## 1. 原始实现状态

原始代码中 ANN 相关逻辑分散在三个位置：

- `backend/app/tasks/index_tasks.py`
  - 负责构建索引
  - 直接调用 FAISS / hnswlib
- `backend/app/services/index_service.py`
  - 负责加载索引到内存
  - 自己判断 Flat、IVF_PQ、HNSW
- `backend/app/services/search_service.py`
  - 负责查询时读取索引
  - 自己做 FAISS / HNSW 查询

原始支持的索引类型：

- `flat`
- `ivf_pq`
- `hnsw`

原始支持的距离度量：

- `l2`
- `ip`
- `cosine`

存在的问题：

- 构建、加载、查询三处逻辑重复，容易不一致。
- 索引参数缺少集中校验。
- cosine 在 FAISS 下需要归一化，原始实现只部分处理。
- IVF_PQ 参数可能在小数据集上直接构建失败。
- 没有稳定生成 `id_map`，查询结果位置和 `cell_id` 映射依赖数据库读取顺序。
- 没有统一 `.meta.json`，不利于追踪索引版本、维度、参数和构建耗时。
- Windows 中文路径下，FAISS 原生文件 I/O 可能打不开绝对路径。

## 2. 当前升级结果

新增统一引擎：

- `backend/app/services/ann_engine.py`

该引擎统一负责：

- 索引参数校验
- 向量矩阵合法性检查
- FAISS Flat 构建
- FAISS IVF_PQ 构建
- HNSWLIB HNSW 构建
- cosine 查询归一化
- 内积/余弦距离语义统一
- 精确检索计算
- 索引加载
- 索引查询
- 生成 `.id_map.json`
- 生成 `.meta.json`

## 3. 产物结构

每次索引构建后会生成：

```text
indices/{dataset_id}/v{version}/flat.index
indices/{dataset_id}/v{version}/flat.id_map.json
indices/{dataset_id}/v{version}/flat.meta.json
```

对于其他索引类型，文件名前缀对应：

- `ivf_pq.index`
- `hnsw.index`

### 3.1 `.index`

底层 ANN 索引文件：

- Flat / IVF_PQ 使用 FAISS 序列化文件
- HNSW 使用 hnswlib 序列化文件

### 3.2 `.id_map.json`

保存索引内部位置和业务细胞编号的稳定映射：

```json
[
  {
    "position": 0,
    "cell_id": "cell_a"
  }
]
```

作用：

- 避免数据库读取顺序变化导致 ANN 结果回查错细胞。
- 让索引文件可以脱离数据库行号独立追踪。

### 3.3 `.meta.json`

保存索引元数据：

```json
{
  "index_id": 1,
  "dataset_id": 1,
  "index_name": "codex_smoke_flat_l2",
  "index_type": "flat",
  "metric_type": "l2",
  "dim": 4,
  "vector_count": 6,
  "params_json": {},
  "file_path": "...",
  "id_map_path": "...",
  "build_seconds": 0.0012,
  "created_at": "..."
}
```

作用：

- 支持索引审计。
- 支持重启后加载 HNSW 时恢复维度。
- 支持性能评测记录。

## 4. 参数校验

当前已集中校验：

### 4.1 通用校验

- `index_type` 必须属于 `flat / ivf_pq / hnsw`
- `metric` 必须属于 `l2 / ip / cosine`
- 向量维度必须大于 0
- 向量数量必须大于 0
- 向量矩阵不能包含 NaN 或 infinity

### 4.2 IVF_PQ 校验

- `nlist` 必须在 `[1, vector_count]`
- `m` 必须能整除向量维度
- `nbits` 必须在 `[4, 12]`
- 训练向量数必须不少于 `2^nbits`
- `nprobe` 必须在 `[1, nlist]`

### 4.3 HNSW 校验

- `M` 必须在 `[4, 128]`
- `ef_construction >= M`
- `ef > 0`

## 5. 查询策略

### 5.1 精确查询

由 `ANNEngine.exact_search()` 统一计算：

- `l2`：平方欧氏距离
- `ip`：负内积，便于按升序取 Top-K
- `cosine`：`1 - cosine_similarity`

### 5.2 近似查询

由 `ANNEngine.search()` 统一执行：

- Flat / IVF_PQ：
  - FAISS `search`
  - cosine 查询向量归一化
  - IP/cosine 分数转换为统一距离语义
- HNSW：
  - hnswlib `knn_query`
  - 支持单次请求 `ef_search`

## 6. 稳定性提升

本次升级解决了以下稳定性问题：

- ANN 构建、加载、查询逻辑统一。
- 索引参数提前校验，避免后台任务运行到一半才失败。
- 索引内部位置和 `cell_id` 显式保存。
- 查询时优先按 `id_map` 重排回查顺序。
- 索引元信息显式落盘。
- Windows 中文路径通过相对路径适配，避免 FAISS 文件 I/O 失败。
- NumPy 版本固定为 `<2`，避免 FAISS wheel ABI 不兼容。

## 7. 是否还能继续升级

可以继续升级，建议方向如下。

### 7.1 元数据过滤优化

当前策略：

- ANN 先取扩大候选集
- 再做 metadata 过滤
- 候选不足时 fallback 到过滤子集精确检索

更高性能方案：

- 为 `cell_type / organ / sample_id` 建 bitmap。
- ANN 结果和 bitmap 做快速交集。
- 对高频过滤字段建立子索引。
- 大数据集下减少 fallback 精确扫描次数。

### 7.2 IVF_PQ 自适应参数

可以根据数据规模自动推荐：

- `nlist`
- `nprobe`
- `m`
- `nbits`

例如：

- 小数据集默认 `flat`
- 中等数据集默认 `hnsw`
- 超大数据集默认 `ivf_pq`

### 7.3 召回率评估升级

当前非 Flat 索引召回率仍是估计值。

可升级为：

- 抽样查询集
- Flat 精确结果作为基准
- 计算 `recall@k`
- 记录平均延迟、p95、p99
- 构建失败或召回率不足时拒绝发布

### 7.4 并发与缓存升级

当前缓存是进程内字典。

可升级为：

- LRU 缓存
- 最大内存限制
- 索引访问时间统计
- 发布/回滚时跨进程缓存失效
- 多 worker 共享索引加载策略

### 7.5 GPU / 分布式索引

如果后续数据规模扩大，可以继续接入：

- FAISS GPU
- 分片索引
- 多进程并行构建
- 分布式向量服务

## 8. 当前结论

当前 ANN 引擎已经从“能构建和搜索”升级为“统一构建、统一校验、统一加载、统一查询、稳定映射、可审计产物”的版本。

对于课程项目阶段，当前版本已经足够支持：

- 后端联调
- E 模块检索演示
- D 模块索引构建演示
- 基础性能评测
- 后续前端可视化对接

如果要进一步冲击“更高效”，优先做元数据过滤 bitmap 和真实 recall@k 评估。

## 9. 自研改进算法：`hnsw_rerank`

`hnsw_rerank` 是在原生 HNSW 之上落地的「召回 + 精排」两阶段改进，目标是同时优化检索精度、查询时间与内存占用。

### 9.1 算法核心

- 召回阶段：使用 HNSW `knn_query(k = top_k * rerank_factor)` 拉宽候选集（默认 `rerank_factor=4`，下限 `MIN_RERANK_FETCH=32`）。
- 精排阶段：在小候选集合 `(<=64)` 内，用 `float32` 精确距离重排，取 Top-K。
  - `l2`：平方欧氏
  - `cosine`：归一化后取 `1 - cosine_similarity`
  - `ip`：负内积
- 内存优化：精排向量可保存为 `float16`（`use_fp16=True`），精排时再 `astype(float32)` 即时还原，相对全量 `float32` 节省 ≈50% 内存。
- 自适应 `ef`：召回阶段会自动把 `ef_search` 抬高到 `max(ef_search, top_k * rerank_factor)`，避免候选窗口不足拉低召回。

### 9.2 实现位置

- 引擎：[ann_engine.py](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/backend/app/services/ann_engine.py)
  - `SUPPORTED_INDEX_TYPES` 加入 `"hnsw_rerank"`
  - `build()` 中保存 `.rerank.npy`（fp16/fp32）
  - `_search_hnsw_rerank()` 实现两阶段检索
- 任务：[index_tasks.py](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/backend/app/tasks/index_tasks.py)
- 校验：`validate_config` 中 `M / ef_construction / ef / rerank_factor / use_fp16` 范围校验
- 基准测试：[benchmark_ann.py](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/backend/scripts/benchmark_ann.py)
  - 新增 `HNSW_RERANK_CONFIGS`、`query_hnsw_rerank()`、`rerank_memory_mb()`
  - 报告新增 `Type / rerank / fp16 / Mem(MB)` 列，便于和 `flat` / `hnsw` 直接对比 `Recall@K`、`P50/P95/P99` 与内存

### 9.3 期望效果

| 维度 | 原生 HNSW | `hnsw_rerank` (fp32) | `hnsw_rerank` (fp16) |
|---|---|---|---|
| 检索精度 (Recall@K) | 受 `ef_search` 影响显著 | 接近 Flat 精确解 | 接近 Flat（精排仍是 fp32） |
| 查询时间 | 最快 | +1 次 (top_k×factor)×dim 矩阵差分 | 同 fp32，多 1 次 `astype` |
| 内存占用 | 仅 HNSW 图 | HNSW 图 + 全量 fp32 副本 | HNSW 图 + **fp16 副本（≈50%）** |

参数推荐：

- 一般场景：`{M:16, ef_construction:120, ef:64, rerank_factor:4, use_fp16:true}`
- 高召回优先：`rerank_factor=8`，`use_fp16=false`
- 内存敏感：`use_fp16=true`，`rerank_factor=4`

### 9.4 验证方式

```bash
cd backend
python scripts/benchmark_ann.py --dataset-id 1 --queries 200 --top-k 10
```

报告位于 `reports/ann_benchmark_<ds>_<ts>.md`，含 `flat` / `hnsw` / `hnsw_rerank_fp32` / `hnsw_rerank_fp16` 四组对比与“最佳推荐”。

## 10. 多数据集联合检索

支持把多个单细胞数据集联合建立一个 ANN 索引，实现跨数据集细胞搜索。

### 10.1 数据模型

- 新增列：`ann_indices.dataset_ids: JSON`（保留原 `dataset_id` 作为主数据集 / 文件路径 / 版本号锚点）
- 迁移：[d18e2a3b9b21_add_dataset_ids_to_ann_indices.py](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/backend/migrations/versions/d18e2a3b9b21_add_dataset_ids_to_ann_indices.py)
  - SQLite 通过 `batch_alter_table` 添加列
  - 旧索引 backfill：`dataset_ids = '[' || dataset_id || ']'`

### 10.2 构建流程

- `POST /indexes` 接收 `dataset_ids: [int, ...]`（或单个 `dataset_id`，自动归一）
- 校验：所有数据集 PCA 维度必须一致，否则拒绝
- 任务：按 `dataset_id ASC, id ASC` 顺序拉取并合并所有数据集向量，整体构建一个 ANN 索引
- `id_map.json` 每个条目同时记录 `cell_id` 与 `dataset_id`，避免不同数据集 `cell_id` 重名导致结果回查错位

### 10.3 查询流程

- `POST /search` 入参变更：
  - `index_id` 必填
  - `dataset_id` 改为可选（联合索引下允许跨数据集）
  - 新增 `source_dataset_id`：指定 cell_id 解析所在数据集（cell_id 跨库重名时必填）
  - 新增 `dataset_ids`：限定结果只来自该子集
- 返回结果每条记录新增 `source_dataset_id`，标识匹配细胞来自哪个数据集
- 响应新增 `index_dataset_ids` 字段，便于前端展示该索引覆盖的全部数据集

### 10.4 涉及文件

- 模型：[ann_index.py](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/backend/app/models/ann_index.py)（`dataset_ids` JSON 列）
- Schema：[schemas/index.py](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/backend/app/schemas/index.py)、[schemas/search.py](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/backend/app/schemas/search.py)
- 服务：[index_service.py](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/backend/app/services/index_service.py)、[search_service.py](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/backend/app/services/search_service.py)
- 任务：[index_tasks.py](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/backend/app/tasks/index_tasks.py)
- 引擎：[ann_engine.py](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/backend/app/services/ann_engine.py) (`write_id_map` 接受 `dataset_ids`、`read_id_map_entries`)
- 前端：[IndexesPage.tsx](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/frontend/src/pages/IndexesPage.tsx)、[SearchPage.tsx](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/frontend/src/pages/SearchPage.tsx)、[types.ts](file:///Users/bytedance/Documents/大三下/软件工程/ann/ANN-retrieval-system/frontend/src/types.ts)

### 10.5 升级数据库

新增列需要运行迁移：

```bash
cd backend
alembic upgrade head
```

旧索引在升级后会被回填为 `dataset_ids=[原 dataset_id]`，单数据集行为完全兼容。
