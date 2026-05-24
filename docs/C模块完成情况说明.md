# C模块完成情况说明

## 1. 模块职责

我负责的 C 模块主要包括以下内容：

- `.h5ad` 数据读取
- 元数据解析
- 向量提取与生成
- 提供向量和元数据
- 提供 `cell_id -> vector` 服务
- 配合后端上传链路完成数据接入

当前实现基于已有后端工程 `ANN-retrieval-system/backend` 进行补充，而不是另起一套独立程序。这样可以直接接入现有的上传、任务调度、索引构建和检索链路。

---

## 2. 当前完成情况

### 2.1 已完成的核心能力

目前已经完成以下核心功能：

- 支持读取 `.h5ad`、`csv`、`mtx` 数据
- 支持对 AnnData 做合法性检查
- 优先使用数据中现成的 `X_pca` 作为检索向量
- 优先使用现成的 `X_umap`、`X_tsne` 作为可视化二维坐标
- 将每个细胞的 PCA 向量写入 `CellVector`
- 将每个细胞的元数据写入 `CellMetadata`
- 支持导出 `processed.h5ad`、`umap.csv`、`tsne.csv`
- 新增独立数据访问层，支持：
  - `cell_id -> vector`
  - `cell_id -> metadata`
  - 批量 `cell_id -> metadata`
- 补充了上传分块的基础完整性校验
- 修正了索引构建和检索时的向量读取顺序问题

### 2.2 目前可以认为已经完成的职责

从“C 模块核心任务”角度看，目前已经基本完成以下职责：

- `h5ad` 读取和处理生成
- 提供向量和元数据
- `cell_id -> vector` 服务
- 基础后端文件上传支持

---

## 3. 针对当前数据的实际结论

根据对当前 `.h5ad` 数据的检查，得到以下结论：

- 细胞数：`69032`
- 基因数：`32397`
- `obs_names` 无重复，可直接作为 `cell_id`
- 存在 `X_pca`，形状为 `(69032, 30)`
- 存在 `X_umap`，形状为 `(69032, 2)`
- 存在 `X_tsne`，形状为 `(69032, 2)`
- 存在关键元数据字段：
  - `cell_type`
  - `sample_id`
  - `disease`
  - `AgeGroup`
  - `tissue`

因此当前数据处理策略已经明确为：

- `cell_id = obs_names`
- 检索主向量 = `obsm["X_pca"]`
- UMAP 展示 = `obsm["X_umap"]`
- t-SNE 展示 = `obsm["X_tsne"]`
- 元数据主字段：
  - `cell_type`
  - `sample_id`
  - `organ <- tissue`
- 其他原始 `obs` 字段保存在 `obs_ext`

---

## 4. 具体改动说明

## 4.1 `preprocess_service.py`

文件：

- `ANN-retrieval-system/backend/app/services/preprocess_service.py`

主要改动如下：

- 新增 `_validate_adata()`，用于检查：
  - `n_obs` 不能为 0
  - `n_vars` 不能为 0
  - `obs_names` 不能为空
  - `obs_names` 不能重复
- 将原来“无条件重新计算 PCA”的逻辑改为：
  - 如果存在 `X_pca`，直接使用
  - 不存在时才重新计算
- 将原来“无条件重新计算 UMAP”的逻辑改为：
  - 如果存在 `X_umap`，直接使用
  - 不存在时才补算
- 新增 `_collect_embedding_methods()`，自动识别：
  - `pca`
  - `umap`
  - `tsne`
- 新增 `_pick_obs_value()`，统一处理元数据字段读取和空值
- 将 `tissue` 映射到 `organ`
- 新增 `_write_embedding_csv()`，统一导出二维 embedding
- 现在会输出：
  - `processed.h5ad`
  - `umap.csv`
  - `tsne.csv`

### 4.2 `data_access_service.py`

文件：

- `ANN-retrieval-system/backend/app/services/data_access_service.py`

这是新建的数据访问服务层，新增了以下方法：

- `get_vector_by_cell_id(dataset_id, cell_id)`
  - 根据 `dataset_id + cell_id` 获取 PCA 向量
- `get_metadata_by_cell_id(dataset_id, cell_id)`
  - 获取单个细胞的元数据
- `get_metadata_by_cell_ids(dataset_id, cell_ids)`
  - 批量获取一组细胞的元数据
  - 并保证返回顺序与输入 `cell_ids` 顺序一致

这部分是我当前实现的“`cell_id -> vector` / `cell_id -> metadata` 服务”的核心。

### 4.3 `search_service.py`

文件：

- `ANN-retrieval-system/backend/app/services/search_service.py`

主要改动如下：

- `_load_query_vector()` 不再直接查 `CellVector`
- 改为调用 `DataAccessService.get_vector_by_cell_id()`
- 检索结果组装时，不再直接查 `CellMetadata`
- 改为调用 `DataAccessService.get_metadata_by_cell_id()`
- 批量读取 `CellVector` 时补了：
  - `order_by(CellVector.id.asc())`

这样做的目的是：

- 让检索模块开始真正复用我写的数据访问服务
- 保证向量顺序在检索阶段稳定

### 4.4 `index_tasks.py`

文件：

- `ANN-retrieval-system/backend/app/tasks/index_tasks.py`

主要改动：

- 在索引构建读取 `CellVector` 时补了：
  - `order_by(CellVector.id.asc())`

这样做是为了和检索阶段保持一致，避免：

- 建索引时使用一套向量顺序
- 检索回查时使用另一套向量顺序

### 4.5 `dataset_service.py`

文件：

- `ANN-retrieval-system/backend/app/services/dataset_service.py`

主要改动如下：

- 上传初始化时，在 `meta.json` 中记录：
  - `chunk_size`
  - `expected_chunks`
- 分块上传时开始记录：
  - `received_chunks`
- 对重复上传的分块进行去重记录
- 完成上传时增加缺块检查：
  - 如果分块未传完整，不允许继续合并文件

这部分使“后端文件上传”从基础可用，提升为带基础完整性校验的版本。

---

## 5. 当前实现的服务能力

我当前已经提供的数据层服务能力包括：

### 5.1 向量服务

- 根据 `cell_id` 获取单个细胞向量
- 当前默认向量类型为 `pca`
- 向量数据类型统一为 `float32`

### 5.2 元数据服务

- 根据 `cell_id` 获取单个细胞元数据
- 根据一批 `cell_id` 批量获取元数据
- 返回字段包括：
  - `cell_id`
  - `cell_type`
  - `organ`
  - `sample_id`
  - `obs_ext`
  - `qc_flags`

### 5.3 数据集处理产物

- `processed.h5ad`
- `umap.csv`
- `tsne.csv`
- `CellVector` 表中的 PCA 向量
- `CellMetadata` 表中的元数据

---

## 6. 需要和 D 同学说明清楚的内容

### 6.1 检索主向量是什么

- 当前 ANN 索引构建使用的向量是：
  - `X_pca`
- 对应数据库中：
  - `CellVector.vector_type = "pca"`
- 当前这份数据的向量维度是：
  - `30`

### 6.2 D 不需要自己再解析 `.h5ad`

D 模块不需要自己读取 `.h5ad` 文件，只需要从数据库中读取：

- `dataset_id`
- `vector_type = "pca"`
- 对应的 `CellVector`

即可完成索引构建。

### 6.3 向量顺序必须保持一致

目前系统中已经统一约定：

- 建索引读取向量时，按 `CellVector.id.asc()` 取数据
- 检索阶段读取向量时，也按 `CellVector.id.asc()` 取数据

D 同学需要明确：

- 不要自己重排向量顺序
- 不要自己重新定义行号映射
- 索引内部第 `i` 个向量默认对应数据库中同顺序的第 `i` 条 `CellVector`

### 6.4 UMAP/t-SNE 不是索引向量

要明确告诉 D：

- `X_umap`
- `X_tsne`

都只是可视化坐标，不是 ANN 检索主向量。

---

## 7. 需要和 E 同学说明清楚的内容

### 7.1 查询向量获取方式

当 E 需要按 `cell_id` 发起查询时：

- 系统会通过 `DataAccessService.get_vector_by_cell_id()` 获取对应 PCA 向量

也就是说，E 可以直接把 `cell_id` 作为查询输入，不需要自己再找原始向量。

### 7.2 查询结果元数据来源

检索结果中返回的以下字段来自 `CellMetadata`：

- `cell_type`
- `organ`
- `sample_id`

其他更完整的元数据在：

- `obs_ext`

### 7.3 `organ` 的真实来源

当前原始数据里没有 `organ` 字段，但有 `tissue` 字段。

所以当前系统中：

- `organ <- tissue`


### 7.4 可视化文件已可直接使用

当前已经能导出：

- `umap.csv`
- `tsne.csv`

所以 E 如果要做：

- 查询点高亮
- 邻居点展示
- 二维可视化结果展示

都可以直接基于这两个文件继续做。

### 7.5 批量结果补 metadata 的能力已经具备

我已经实现：

- `get_metadata_by_cell_ids(dataset_id, cell_ids)`

因此 E 如果后面要对一批 ANN 结果统一补元数据，可以直接复用这部分服务。

---


