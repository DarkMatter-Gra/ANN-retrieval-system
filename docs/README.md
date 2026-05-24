# 项目文档总览

本目录集中存放项目报告、参考资料以及 E 模块“查询检索服务 + 测试文档演示”相关交付材料。

## 文档列表

| 文档 | 内容 |
|---|---|
| `report.tex` | 软件开发报告 LaTeX 骨架 |
| `E模块交付说明.md` | E 模块职责范围、已完成代码、接口能力、当前边界 |
| `E模块测试报告.md` | 测试目标、测试环境、测试数据、测试用例、测试结论 |
| `ANN引擎实现与升级说明.md` | 当前 ANN 算法实现、存在问题、升级后的统一 ANN 引擎、后续优化方向 |
| `ANN_API_文档_工程内最新版.md` | 当前工程内 API 文档副本 |
| `C模块完成情况说明.md` | C 数据处理模块完成说明 |
| `D模块完成总结.md` | D ANN 索引模块完成总结 |
| `需求分析文档_lab2.pdf` | 需求分析阶段 PDF |
| `软件设计文档_第三次作业.pdf` | 软件设计阶段 PDF |

## 图片材料

| 文件 | 内容 |
|---|---|
| `NKU.png` | 报告封面校徽图片 |
| `分工.png` | 小组分工图片 |
| `报告要求.png` | 报告结构要求截图 |

## 关联工程文件

| 文件 | 说明 |
|---|---|
| `../backend/app/services/search_service.py` | E 模块核心查询检索服务 |
| `../backend/app/services/ann_engine.py` | 统一 ANN 引擎 |
| `../backend/app/api/v1/files.py` | 批量检索结果下载接口 |
| `../backend/scripts/smoke_backend.py` | 后端核心链路烟测脚本 |
| `../backend/tests/test_e_search_flow.py` | E 模块自动化测试 |
| `../ANN_API_文档.md` | 后端 API 总文档 |

## 验证命令

在 `backend/` 目录执行：

```bash
python scripts/smoke_backend.py
python -m pytest
```

当前验证结论：

```text
smoke_backend.py 通过
pytest: 4 passed
```

## 演示接口入口

本地服务启动后：

```text
API: http://127.0.0.1:8000
Swagger: http://127.0.0.1:8000/docs
```

测试账号：

```text
username: codex_smoke_user
password: SmokePass123
```
