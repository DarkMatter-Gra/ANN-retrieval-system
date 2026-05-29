# ANN 性能基准测试报告

## 1. 测试目标

验证当前 ANN 引擎在老师提供的真实 `liver.h5ad` 数据上是否具备足够的检索效率和召回质量，并为后续报告中的“算法升级与性能评估”提供实测证据。

本次测试采用 Flat 精确检索作为基准，比较不同 HNSW 参数配置下的：

- `recall@10`
- 平均检索延迟
- p50 / p95 / p99 延迟
- 索引构建耗时

## 2. 测试数据与方法

数据集：

| 项目 | 数值 |
|---|---:|
| 数据集名称 | `liver_real_test` |
| 细胞数 | 69032 |
| 基因数 | 32397 |
| 向量来源 | `X_pca` |
| 向量维度 | 30 |
| 距离度量 | L2 |
| Top-K | 10 |
| 抽样查询数 | 200 |
| 随机种子 | 42 |

测试命令：

```powershell
cd backend
$env:PYTHONPATH='.'
python scripts\benchmark_ann.py --dataset-id 1 --queries 200 --top-k 10
```

## 3. 测试结果

| 方法 | 参数 | ef_search | 构建耗时(s) | recall@10 | 平均延迟(ms) | p50(ms) | p95(ms) | p99(ms) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Flat 精确检索 | `{}` | - | 0.0000 | 1.0000 | 3.6538 | 3.5615 | 4.6090 | 5.5304 |
| HNSW Fast | `M=8, ef_construction=80` | 16 | 0.2986 | 0.9520 | 0.0124 | 0.0119 | 0.0156 | 0.0219 |
| HNSW Fast | `M=8, ef_construction=80` | 32 | 0.2986 | 0.9840 | 0.0147 | 0.0146 | 0.0189 | 0.0207 |
| HNSW Fast | `M=8, ef_construction=80` | 64 | 0.2986 | 0.9925 | 0.0212 | 0.0212 | 0.0255 | 0.0285 |
| HNSW Balanced | `M=16, ef_construction=120` | 32 | 0.4072 | 0.9945 | 0.0222 | 0.0217 | 0.0293 | 0.0357 |
| HNSW Balanced | `M=16, ef_construction=120` | 64 | 0.4072 | 0.9970 | 0.0274 | 0.0277 | 0.0347 | 0.0381 |
| HNSW Balanced | `M=16, ef_construction=120` | 128 | 0.4072 | 0.9985 | 0.0517 | 0.0502 | 0.0693 | 0.0778 |
| HNSW Quality | `M=32, ef_construction=200` | 64 | 0.6311 | 0.9990 | 0.0415 | 0.0390 | 0.0606 | 0.0816 |
| HNSW Quality | `M=32, ef_construction=200` | 128 | 0.6311 | 0.9995 | 0.0565 | 0.0560 | 0.0730 | 0.0848 |
| HNSW Quality | `M=32, ef_construction=200` | 256 | 0.6311 | 1.0000 | 0.0968 | 0.0961 | 0.1345 | 0.1478 |

## 4. 结果分析

Flat 精确检索作为 baseline，`recall@10=1.0`，平均延迟约 `3.65 ms`，p95 延迟约 `4.61 ms`。

HNSW 在召回率接近或达到 1.0 的情况下，延迟明显低于 Flat 精确检索：

- `HNSW Fast, ef_search=64`：`recall@10=0.9925`，p95 约 `0.0255 ms`
- `HNSW Balanced, ef_search=128`：`recall@10=0.9985`，p95 约 `0.0693 ms`
- `HNSW Quality, ef_search=256`：`recall@10=1.0000`，p95 约 `0.1345 ms`

在当前数据规模下，HNSW 构建耗时也较低，三个配置分别约为 `0.30s`、`0.41s`、`0.63s`。

## 5. 参数建议

如果演示和报告更强调准确性，建议使用：

```json
{
  "index_type": "hnsw",
  "metric": "l2",
  "params_json": {
    "M": 32,
    "ef_construction": 200,
    "ef": 256
  }
}
```

如果更强调速度和构建成本，建议使用：

```json
{
  "index_type": "hnsw",
  "metric": "l2",
  "params_json": {
    "M": 16,
    "ef_construction": 120,
    "ef": 128
  }
}
```

## 6. 结论

当前 ANN 引擎已经不只是“能检索”，而是可以在真实数据上完成可量化的高召回、低延迟近似检索。基于本次 benchmark，HNSW 是当前项目阶段最合适的默认 ANN 索引方案；Flat 精确检索适合作为小数据集和 recall 评估基准。
