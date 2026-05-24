## 版本说明

> 本文档用于 ANN 检索系统后端 API 统一交付。

| 项目 | 内容 | 说明 |
| --- | --- | --- |
| 适用环境 | 开发环境 | Base URL：`http://localhost:8000/api/v1` |
| 时间格式 | ISO 8601 UTC | 示例：`2026-05-21T14:00:00Z` |
| 分页约定 | `page` 从 1 开始，`page_size` 默认 20 | `page_size` 最大 100 |

## 基本规范

### 1. 接口访问约定

| 规范项 | 说明 |
| --- | --- |
| Base URL | `http://localhost:8000/api/v1` |
| 鉴权方式 | 除注册、登录接口外，所有接口均需在请求 Header 中携带 `Authorization: Bearer <token>` |
| 响应包装 | 所有接口统一返回 `code`、`message`、`data` 三层结构 |
| 文件上传限制 | 单次上传文件最大 2GB；超过建议使用分块上传链路 |
| 检索任务模型 | 预处理、索引构建、批量检索、报告导出均采用异步任务机制，通过 `/tasks/{task_id}` 轮询任务状态 |

### 2. 统一响应格式

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

### 3. 错误码规范

| 错误码范围 | 类别 | 说明 |
| --- | --- | --- |
| `0` | 成功 | 请求处理成功 |
| `400xx` | 参数错误 | `40001` 参数缺失，`40002` 参数格式错误，`40003` 参数超限 |
| `401xx` | 鉴权失败 | `40101` Token 缺失或账号/密码错误，`40102` Token 过期，`40103` Token 非法 |
| `403xx` | 权限不足 | `40301` 角色权限不足或账号已锁定，`40302` 资源无权访问，`40303` 配额超限 |
| `404xx` | 资源不存在 | `40401` 用户不存在，`40402` 数据集不存在，`40403` 索引不存在，`40404` 任务不存在 |
| `409xx` | 业务冲突 | `40901` 用户名已存在（本版在注册接口中使用） |
| `500xx` | 服务端错误 | `50001` 内部错误，`50002` 数据库错误，`50003` 检索引擎错误，`50004` 文件系统错误 |

### 4. 模块目录

| 模块 | 路径前缀 | 内容说明 |
| --- | --- | --- |
| 用户与鉴权 | `/auth`、`/users` | 注册、登录、当前用户信息、管理员侧用户管理 |
| 数据管理 | `/datasets` | 数据上传、预处理触发、列表查询、详情与日志查看 |
| 索引构建 | `/indexes` | 索引创建、查看、加载、回滚、上线 |
| 检索任务 | `/search`、`/batch-search`、`/tasks` | 单次检索、批量检索、任务轮询、结果导出 |
| 可视化与指标 | `/visualizations`、`/metrics`、`/reports` | Embedding 点位、检索高亮、性能指标、诊断报告 |

---

## 一、用户与鉴权模块（`/auth`、`/users`）

### 1.1 用户注册

- **接口名称：** 用户注册

- **请求方式 + 路径：** `POST /auth/register`

- **权限要求：** 无需鉴权

- **接口说明：** 创建新用户账号，并指定初始角色。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 用户名，长度 3-64，建议仅使用字母、数字、下划线 |
| `password` | string | 是 | 密码，长度 8-128 |
| `role` | enum | 是 | 可选值：`admin`、`dev`、`user`、`readonly`、`service`、`auditor` |
| `email` | string | 是 | 邮箱地址，用于账号绑定与通知 |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `code` | int | 业务状态码，成功时为 `0` |
| `message` | string | 响应消息，成功时通常为 `ok` |
| `data.user_id` | int | 新创建的用户 ID |
| `data.username` | string | 注册成功后的用户名 |
| `data.role` | string | 用户角色 |

**请求示例**

```json
{
  "method": "POST",
  "path": "/auth/register",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "username": "alice",
    "password": "Passw0rd!",
    "role": "user",
    "email": "alice@example.com"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user_id": 1,
    "username": "alice",
    "role": "user"
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40001` | 请求体字段缺失 |
| `40002` | 用户名、密码、邮箱或角色格式不合法 |
| `40901` | 用户名已存在 |

### 1.2 用户登录

- **接口名称：** 用户登录

- **请求方式 + 路径：** `POST /auth/login`

- **权限要求：** 无需鉴权

- **接口说明：** 校验用户名密码，登录成功后返回访问令牌与默认控制台路由。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 登录用户名 |
| `password` | string | 是 | 登录密码 |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `code` | int | 业务状态码 |
| `message` | string | 响应消息 |
| `data.access_token` | string | JWT 或等价访问令牌 |
| `data.expire_at` | string | 令牌过期时间，ISO 8601 UTC |
| `data.role` | string | 当前用户角色 |
| `data.dashboard_route` | string | 登录后默认跳转路由 |

**请求示例**

```json
{
  "method": "POST",
  "path": "/auth/login",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "username": "alice",
    "password": "Passw0rd!"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "access_token": "eyJ...",
    "expire_at": "2026-05-23T11:00:00Z",
    "role": "user",
    "dashboard_route": "/dashboard/user"
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40101` | 账号或密码错误 |
| `40301` | 账号已锁定（连续失败 3 次触发锁定） |

### 1.3 获取当前用户信息

- **接口名称：** 获取当前用户信息

- **请求方式 + 路径：** `GET /auth/me`

- **权限要求：** 所有已登录角色

- **接口说明：** 获取当前登录用户的基础信息、配额与菜单权限。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.user_id` | int | 当前用户 ID |
| `data.username` | string | 当前用户名 |
| `data.role` | string | 当前角色 |
| `data.quota.used` | int | 已使用配额 |
| `data.quota.limit` | int | 总配额上限 |
| `data.menus[]` | string[] | 当前角色可见的菜单编码 |

**请求示例**

```json
{
  "method": "GET",
  "path": "/auth/me",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user_id": 1,
    "username": "alice",
    "role": "user",
    "quota": {
      "used": 3,
      "limit": 10
    },
    "menus": [
      "dataset",
      "search",
      "visualization"
    ]
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40101` | Token 缺失 |
| `40102` | Token 已过期 |
| `40103` | Token 非法 |

### 1.4 管理员修改用户

- **接口名称：** 管理员修改用户

- **请求方式 + 路径：** `PATCH /users/{user_id}`

- **权限要求：** `admin`

- **接口说明：** 管理员更新目标用户角色、配额或状态。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `user_id (Path)` | int | 是 | 目标用户 ID |
| `Authorization (Header)` | string | 是 | 管理员 Token |
| `role` | string | 否 | 更新后的角色，如 `dev` |
| `quota` | int | 否 | 更新后的配额上限 |
| `status` | string | 否 | 用户状态，示例：`active` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.user_id` | int | 被修改的用户 ID |
| `data.updated_fields[]` | string[] | 本次实际更新的字段集合 |

**请求示例**

```json
{
  "method": "PATCH",
  "path": "/users/1",
  "headers": {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  },
  "body": {
    "role": "dev",
    "quota": 20,
    "status": "active"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user_id": 1,
    "updated_fields": [
      "role",
      "quota"
    ]
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40002` | 字段格式错误，例如角色或状态不合法 |
| `40101` / `40102` / `40103` | Token 缺失、过期或非法 |
| `40301` | 当前角色不是管理员 |
| `40401` | 目标用户不存在 |

### 1.5 重置用户密码

- **接口名称：** 重置用户密码

- **请求方式 + 路径：** `POST /users/{user_id}/reset-password`

- **权限要求：** `admin` 或用户本人

- **接口说明：** 管理员可重置任意用户密码，普通用户仅可重置自己的密码。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `user_id (Path)` | int | 是 | 目标用户 ID |
| `Authorization (Header)` | string | 是 | 当前登录用户 Token |
| `new_password` | string | 是 | 新密码，长度 8-128 |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.user_id` | int | 被重置密码的用户 ID |
| `data.result` | string | 执行结果，成功时为 `success` |

**请求示例**

```json
{
  "method": "POST",
  "path": "/users/1/reset-password",
  "headers": {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  },
  "body": {
    "new_password": "NewPassw0rd!"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user_id": 1,
    "result": "success"
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40002` | 新密码格式不符合要求 |
| `40101` / `40102` / `40103` | Token 缺失、过期或非法 |
| `40302` | 非管理员且尝试重置他人密码 |
| `40401` | 目标用户不存在 |

### 1.6 删除用户

- **接口名称：** 删除用户

- **请求方式 + 路径：** `DELETE /users/{user_id}`

- **权限要求：** `admin`

- **接口说明：** 删除用户，并级联删除其所有数据集、索引和任务记录。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `user_id (Path)` | int | 是 | 目标用户 ID |
| `Authorization (Header)` | string | 是 | 管理员 Token |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.user_id` | int | 被删除的用户 ID |
| `data.deleted` | boolean | 是否删除成功 |

**请求示例**

```json
{
  "method": "DELETE",
  "path": "/users/1",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user_id": 1,
    "deleted": true
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40101` / `40102` / `40103` | Token 缺失、过期或非法 |
| `40301` | 当前角色不是管理员 |
| `40401` | 目标用户不存在 |
| `50002` | 级联删除过程中数据库操作失败 |

---

## 二、数据管理模块（`/datasets`）

### 2.1 初始化分块上传

- **接口名称：** 初始化分块上传

- **请求方式 + 路径：** `POST /datasets/upload/init`

- **权限要求：** `admin` / `dev` / `user`

- **接口说明：** 创建上传会话，返回上传 ID 和推荐分块大小。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |
| `filename` | string | 是 | 原始文件名，例如 `pbmc3k.h5ad` |
| `size` | int | 是 | 文件大小，单位 bytes |
| `format` | string | 是 | 支持：`h5ad`、`mtx`、`csv` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.upload_id` | string | 上传会话 ID |
| `data.chunk_size` | int | 建议分块大小，单位 bytes |

**请求示例**

```json
{
  "method": "POST",
  "path": "/datasets/upload/init",
  "headers": {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  },
  "body": {
    "filename": "pbmc3k.h5ad",
    "size": 52428800,
    "format": "h5ad"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "upload_id": "up_abc123",
    "chunk_size": 5242880
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40002` | 文件格式不支持或文件名非法 |
| `40003` | 文件大小超过上限 |
| `40101` / `40102` / `40103` | Token 缺失、过期或非法 |
| `40303` | 用户上传配额超限 |

### 2.2 上传分块

- **接口名称：** 上传分块

- **请求方式 + 路径：** `POST /datasets/upload/chunk`

- **权限要求：** `admin` / `dev` / `user`

- **接口说明：** 按顺序上传文件分块，`chunk_index` 从 0 开始。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |
| `Content-Type (Header)` | string | 是 | 固定为 `multipart/form-data` |
| `upload_id (FormData)` | string | 是 | 初始化上传接口返回的上传会话 ID |
| `chunk_index (FormData)` | int | 是 | 分块索引，从 0 开始递增 |
| `chunk_data (FormData)` | file | 是 | 当前分块的二进制文件内容 |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.received` | boolean | 服务端是否成功接收当前分块 |
| `data.next_chunk` | int | 下一个应上传的分块索引 |

**请求示例**

```json
{
  "method": "POST",
  "path": "/datasets/upload/chunk",
  "headers": {
    "Authorization": "Bearer <token>",
    "Content-Type": "multipart/form-data"
  },
  "form_data": {
    "upload_id": "up_abc123",
    "chunk_index": 0,
    "chunk_data": "<binary file>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "received": true,
    "next_chunk": 1
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40001` | 缺少 `upload_id`、`chunk_index` 或 `chunk_data` |
| `40002` | 分块索引格式错误或表单格式不正确 |
| `40402` | 上传会话不存在或已失效 |
| `50004` | 文件系统写入分块失败 |

### 2.3 完成上传并触发预处理

- **接口名称：** 完成上传并触发预处理

- **请求方式 + 路径：** `POST /datasets/upload/complete`

- **权限要求：** `admin` / `dev` / `user`

- **接口说明：** 合并上传分块，完成文件落盘，并触发格式校验、质控与预处理异步任务。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |
| `upload_id` | string | 是 | 上传会话 ID |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.dataset_id` | int | 新生成的数据集 ID |
| `data.task_id` | string | 预处理异步任务 ID |
| `data.status` | string | 初始状态，示例：`preprocessing` |

**请求示例**

```json
{
  "method": "POST",
  "path": "/datasets/upload/complete",
  "headers": {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  },
  "body": {
    "upload_id": "up_abc123"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "dataset_id": 12,
    "task_id": "task_xyz",
    "status": "preprocessing"
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40001` | 缺少 `upload_id` |
| `40402` | 上传会话不存在或上传未完成 |
| `50003` | 预处理流水线触发失败 |

### 2.4 获取数据集列表

- **接口名称：** 获取数据集列表

- **请求方式 + 路径：** `GET /datasets`

- **权限要求：** `admin` / `dev` / `user` / `readonly` / `auditor`

- **接口说明：** 分页查询数据集列表，支持关键字筛选。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |
| `page (Query)` | int | 否 | 页码，从 1 开始，默认 1 |
| `page_size (Query)` | int | 否 | 每页数量，默认 20，最大 100 |
| `keyword (Query)` | string | 否 | 按数据集名称或相关关键词模糊过滤 |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.list[]` | object[] | 数据集列表 |
| `data.list[].dataset_id` | int | 数据集 ID |
| `data.list[].dataset_name` | string | 数据集名称 |
| `data.list[].file_format` | string | 文件格式 |
| `data.list[].cell_count` | int | 细胞数量 |
| `data.list[].gene_count` | int | 基因数量 |
| `data.list[].qc_status` | string | 质控状态 |
| `data.list[].preprocess_status` | string | 预处理状态 |
| `data.list[].feature_dim` | int | 特征维度 |
| `data.list[].created_at` | string | 创建时间 |
| `data.total` | int | 符合条件的数据集总数 |

**请求示例**

```json
{
  "method": "GET",
  "path": "/datasets?page=1&page_size=20&keyword=pbmc",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "dataset_id": 12,
        "dataset_name": "pbmc3k",
        "file_format": "h5ad",
        "cell_count": 2700,
        "gene_count": 13714,
        "qc_status": "passed",
        "preprocess_status": "done",
        "feature_dim": 50,
        "created_at": "2026-05-21T14:00:00Z"
      }
    ],
    "total": 5
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40002` | 分页参数或关键字格式错误 |
| `40003` | `page_size` 超出最大限制 |
| `40101` / `40102` / `40103` | Token 缺失、过期或非法 |

### 2.5 获取数据集详情

- **接口名称：** 获取数据集详情

- **请求方式 + 路径：** `GET /datasets/{dataset_id}`

- **权限要求：** `admin` / `dev` / `user` / `readonly` / `auditor`

- **接口说明：** 查询数据集元信息、质控报告和预处理状态。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `dataset_id (Path)` | int | 是 | 数据集 ID |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.dataset_info` | object | 数据集基础信息对象，字段结构与系统数据模型一致 |
| `data.qc_report.cells_before` | int | 质控前细胞数量 |
| `data.qc_report.cells_after` | int | 质控后细胞数量 |
| `data.qc_report.mt_ratio_threshold` | float | 线粒体比例阈值 |
| `data.qc_report.doublet_removed` | int | 移除的 doublet 数量 |
| `data.preprocess_status` | string | 预处理状态 |

**请求示例**

```json
{
  "method": "GET",
  "path": "/datasets/12",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "dataset_info": {
      "dataset_id": 12,
      "dataset_name": "pbmc3k",
      "file_format": "h5ad"
    },
    "qc_report": {
      "cells_before": 2800,
      "cells_after": 2700,
      "mt_ratio_threshold": 0.2,
      "doublet_removed": 100
    },
    "preprocess_status": "done"
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40101` / `40102` / `40103` | Token 缺失、过期或非法 |
| `40302` | 当前用户无权访问目标数据集 |
| `40402` | 数据集不存在 |

### 2.6 删除数据集

- **接口名称：** 删除数据集

- **请求方式 + 路径：** `DELETE /datasets/{dataset_id}`

- **权限要求：** `admin` / `dev` / `user`（仅限本人数据集）

- **接口说明：** 删除数据集及其关联的元数据、向量与 ANN 索引信息。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `dataset_id (Path)` | int | 是 | 数据集 ID |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.dataset_id` | int | 被删除的数据集 ID |
| `data.cascade_deleted.cell_metadata` | int | 被级联删除的细胞元数据条数 |
| `data.cascade_deleted.cell_vectors` | int | 被级联删除的细胞向量条数 |
| `data.cascade_deleted.ann_indices` | int | 被删除的 ANN 索引数量 |

**请求示例**

```json
{
  "method": "DELETE",
  "path": "/datasets/12",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "dataset_id": 12,
    "cascade_deleted": {
      "cell_metadata": 2700,
      "cell_vectors": 2700,
      "ann_indices": 3
    }
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40101` / `40102` / `40103` | Token 缺失、过期或非法 |
| `40302` | 当前用户无权删除目标数据集 |
| `40402` | 数据集不存在 |
| `50002` / `50004` | 级联删除过程中出现数据库或文件系统错误 |

### 2.7 获取预处理日志

- **接口名称：** 获取预处理日志

- **请求方式 + 路径：** `GET /datasets/{dataset_id}/logs`

- **权限要求：** `admin` / `dev` / `user` / `readonly` / `auditor`

- **接口说明：** 获取数据集格式校验、质控与预处理各阶段执行日志。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `dataset_id (Path)` | int | 是 | 数据集 ID |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.steps[]` | object[] | 预处理步骤日志数组 |
| `data.steps[].step` | string | 步骤名称，如 `format_check`、`qc`、`preprocess` |
| `data.steps[].status` | string | 步骤执行状态 |
| `data.steps[].duration_ms` | int | 耗时，单位毫秒 |
| `data.warnings[]` | string[] | 预处理告警信息 |
| `data.errors[]` | string[] | 预处理错误信息 |

**请求示例**

```json
{
  "method": "GET",
  "path": "/datasets/12/logs",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "steps": [
      {
        "step": "format_check",
        "status": "done",
        "duration_ms": 120
      },
      {
        "step": "qc",
        "status": "done",
        "duration_ms": 3400
      },
      {
        "step": "preprocess",
        "status": "done",
        "duration_ms": 15000
      }
    ],
    "warnings": [
      "线粒体比例偏高，已过滤50个细胞"
    ],
    "errors": []
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40101` / `40102` / `40103` | Token 缺失、过期或非法 |
| `40302` | 当前用户无权查看目标数据集日志 |
| `40402` | 数据集不存在 |

---

## 三、索引构建模块（`/indexes`）

### 3.1 创建索引构建任务

- **接口名称：** 创建索引构建任务

- **请求方式 + 路径：** `POST /indexes`

- **权限要求：** `admin` / `dev`

- **接口说明：** 基于指定数据集创建索引构建异步任务，支持 `flat`、`ivf_pq`、`hnsw` 三类索引。

> `params_json` 需与 `index_type` 严格匹配：`flat` 无必填参数，`ivf_pq` 需要 `nlist`、`m`、`nbits`，`hnsw` 需要 `M`、`ef_construction`。别把参数随手乱塞，不然调试的人会想顺着网线来找你。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |
| `dataset_id` | int | 是 | 目标数据集 ID |
| `index_name` | string | 是 | 索引名称，建议具备可读性与版本含义 |
| `index_type` | enum | 是 | 可选：`flat`、`ivf_pq`、`hnsw` |
| `metric` | enum | 是 | 可选：`l2`、`cosine`、`ip` |
| `params_json` | object | 是 | 索引参数对象，内容取决于 `index_type` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.index_id` | int | 索引 ID |
| `data.task_id` | string | 构建任务 ID |
| `data.status` | string | 任务初始状态，如 `pending` |

**请求示例**

```json
{
  "method": "POST",
  "path": "/indexes",
  "headers": {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  },
  "body": {
    "dataset_id": 12,
    "index_name": "pbmc3k_hnsw_v1",
    "index_type": "hnsw",
    "metric": "cosine",
    "params_json": {
      "M": 16,
      "ef_construction": 200
    }
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "index_id": 7,
    "task_id": "task_build_001",
    "status": "pending"
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40001` | 缺少必要字段，如 `dataset_id` 或 `index_type` |
| `40002` | 索引类型、距离度量或参数结构不合法 |
| `40301` | 当前角色无索引构建权限 |
| `40402` | 目标数据集不存在 |
| `50003` | 索引构建任务提交到检索引擎失败 |

### 3.2 获取索引列表

- **接口名称：** 获取索引列表

- **请求方式 + 路径：** `GET /indexes`

- **权限要求：** `admin` / `dev`

- **接口说明：** 按数据集和状态过滤查询索引列表。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |
| `dataset_id (Query)` | int | 否 | 按数据集 ID 过滤 |
| `status (Query)` | string | 否 | 构建状态过滤，可选：`pending`、`running`、`done`、`failed` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.list[]` | object[] | 索引列表 |
| `data.list[].index_id` | int | 索引 ID |
| `data.list[].index_name` | string | 索引名称 |
| `data.list[].index_type` | string | 索引类型 |
| `data.list[].metric_type` | string | 距离度量类型 |
| `data.list[].version_no` | int | 版本号 |
| `data.list[].build_status` | string | 构建状态 |
| `data.list[].publish_status` | string | 发布状态，如 `published` |
| `data.list[].recall_score` | float | 召回率评估分数 |
| `data.list[].memory_cost_mb` | float | 内存占用，单位 MB |
| `data.list[].is_loaded` | boolean | 是否已加载到内存 |
| `data.total` | int | 索引总数 |

**请求示例**

```json
{
  "method": "GET",
  "path": "/indexes?dataset_id=12&status=published",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "index_id": 7,
        "index_name": "pbmc3k_hnsw_v1",
        "index_type": "hnsw",
        "metric_type": "cosine",
        "version_no": 1,
        "build_status": "done",
        "publish_status": "published",
        "recall_score": 0.973,
        "memory_cost_mb": 45.2,
        "is_loaded": true
      }
    ],
    "total": 3
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40002` | 筛选参数格式错误 |
| `40301` | 当前角色无索引管理查看权限 |

### 3.3 获取索引详情

- **接口名称：** 获取索引详情

- **请求方式 + 路径：** `GET /indexes/{index_id}`

- **权限要求：** `admin` / `dev`

- **接口说明：** 查询索引元数据、版本信息、召回率和内存使用情况。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `index_id (Path)` | int | 是 | 索引 ID |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.index_meta` | object | 索引元信息 |
| `data.version` | int | 当前版本号 |
| `data.recall` | float | 索引召回率 |
| `data.memory_usage` | float | 内存使用量，单位 MB |

**请求示例**

```json
{
  "method": "GET",
  "path": "/indexes/7",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "index_meta": {
      "index_id": 7,
      "index_name": "pbmc3k_hnsw_v1",
      "index_type": "hnsw"
    },
    "version": 1,
    "recall": 0.973,
    "memory_usage": 45.2
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40301` | 当前角色无索引管理查看权限 |
| `40403` | 索引不存在 |

### 3.4 加载索引到内存

- **接口名称：** 加载索引到内存

- **请求方式 + 路径：** `POST /indexes/{index_id}/load`

- **权限要求：** `admin` / `dev`

- **接口说明：** 将指定索引加载到内存槽位，供在线检索使用。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `index_id (Path)` | int | 是 | 索引 ID |
| `Authorization (Header)` | string | 是 | 管理员或开发者 Token |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.index_id` | int | 被加载的索引 ID |
| `data.loaded` | boolean | 是否加载成功 |
| `data.memory_slot` | int | 内存槽位编号 |

**请求示例**

```json
{
  "method": "POST",
  "path": "/indexes/7/load",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "index_id": 7,
    "loaded": true,
    "memory_slot": 2
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40301` | 当前角色无加载索引权限 |
| `40403` | 索引不存在 |
| `50003` | 检索引擎加载索引失败 |

### 3.5 回滚索引版本

- **接口名称：** 回滚索引版本

- **请求方式 + 路径：** `POST /indexes/{index_id}/rollback`

- **权限要求：** `admin`

- **接口说明：** 将目标索引回滚到指定历史版本，并设置为当前有效版本。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `index_id (Path)` | int | 是 | 索引 ID |
| `Authorization (Header)` | string | 是 | 管理员 Token |
| `target_version` | int | 是 | 目标回滚版本号 |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.index_id` | int | 索引 ID |
| `data.active_version` | int | 当前生效版本号 |

**请求示例**

```json
{
  "method": "POST",
  "path": "/indexes/7/rollback",
  "headers": {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  },
  "body": {
    "target_version": 1
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "index_id": 7,
    "active_version": 1
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40301` | 当前角色无版本回滚权限 |
| `40403` | 索引不存在或目标版本不存在 |
| `50003` | 回滚操作下发至检索引擎失败 |

### 3.6 上线索引

- **接口名称：** 上线索引

- **请求方式 + 路径：** `POST /indexes/{index_id}/publish`

- **权限要求：** `admin`

- **接口说明：** 将索引发布为当前线上版本，并记录审核备注。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `index_id (Path)` | int | 是 | 索引 ID |
| `Authorization (Header)` | string | 是 | 管理员 Token |
| `audit_comment` | string | 是 | 审核意见，例如召回率验证结果与上线说明 |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.index_id` | int | 索引 ID |
| `data.published` | boolean | 是否成功上线 |

**请求示例**

```json
{
  "method": "POST",
  "path": "/indexes/7/publish",
  "headers": {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  },
  "body": {
    "audit_comment": "召回率验证通过，上线生产"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "index_id": 7,
    "published": true
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40001` | 缺少审核备注 `audit_comment` |
| `40301` | 当前角色无索引上线权限 |
| `40403` | 索引不存在 |
| `50003` | 检索引擎发布索引失败 |

---

## 四、查询检索模块（`/search`、`/batch-search`、`/tasks`）

### 4.1 单次检索

- **接口名称：** 单次检索

- **请求方式 + 路径：** `POST /search`

- **权限要求：** `admin` / `dev` / `user` / `readonly` / `service` / `auditor`

- **接口说明：** 支持基于 `cell_id` 或向量执行单次近似/精确检索，可附带过滤条件与检索参数。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |
| `dataset_id` | int | 是 | 数据集 ID |
| `index_id` | int | 是 | 索引 ID |
| `query_type` | enum | 是 | 可选：`cell_id`、`vector` |
| `cell_id` | string | 条件必填 | 当 `query_type=cell_id` 时必填 |
| `vector` | float[] | 条件必填 | 当 `query_type=vector` 时必填 |
| `top_k` | int | 是 | 返回结果数量 |
| `mode` | enum | 是 | 可选：`exact`（精确 Flat）、`ann`（近似检索） |
| `metric` | enum | 是 | 可选：`l2`、`cosine`、`ip` |
| `filters` | object | 否 | 标签过滤条件，如 `cell_type`、`organ` |
| `ef_search` | int | 否 | HNSW 等 ANN 检索运行参数 |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.query_id` | string | 本次检索的查询 ID |
| `data.latency_ms` | int | 检索耗时，单位毫秒 |
| `data.recall_estimate` | float | 召回率估计值 |
| `data.results[]` | object[] | 检索结果列表 |
| `data.results[].rank` | int | 排名 |
| `data.results[].cell_id` | string | 命中细胞 ID |
| `data.results[].score` | float | 相似度得分 |
| `data.results[].distance` | float | 距离值 |
| `data.results[].cell_type` | string | 细胞类型标签 |
| `data.results[].organ` | string | 器官标签 |
| `data.highlight_points.query` | float[] | 查询点二维投影坐标 |
| `data.highlight_points.neighbors[]` | float[][] | 邻居点二维投影坐标 |

**请求示例**

```json
{
  "method": "POST",
  "path": "/search",
  "headers": {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  },
  "body": {
    "dataset_id": 12,
    "index_id": 7,
    "query_type": "cell_id",
    "cell_id": "cell_000981",
    "top_k": 20,
    "mode": "ann",
    "metric": "cosine",
    "filters": {
      "cell_type": [
        "T_cell"
      ],
      "organ": [
        "lung"
      ]
    },
    "ef_search": 128
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "query_id": "q_20260521_001",
    "latency_ms": 486,
    "recall_estimate": 0.963,
    "results": [
      {
        "rank": 1,
        "cell_id": "cell_018723",
        "score": 0.9841,
        "distance": 0.0159,
        "cell_type": "T_cell",
        "organ": "lung"
      }
    ],
    "highlight_points": {
      "query": [0.128, -1.205],
      "neighbors": [[0.121, -1.19], [0.145, -1.167]]
    }
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40001` | 缺少必要参数，如 `dataset_id`、`index_id` 或查询输入 |
| `40002` | 查询类型、度量方式、过滤条件或向量格式错误 |
| `40003` | `top_k` 或 `ef_search` 超限 |
| `40303` | 用户检索配额超限 |
| `40402` / `40403` | 数据集或索引不存在 |
| `50003` | 检索引擎执行失败 |

### 4.2 批量检索（异步）

- **接口名称：** 批量检索

- **请求方式 + 路径：** `POST /batch-search`

- **权限要求：** `admin` / `dev` / `user` / `service`

- **接口说明：** 提交批量检索异步任务，任务完成后可通过导出接口下载结果。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |
| `dataset_id` | int | 是 | 数据集 ID |
| `index_id` | int | 是 | 索引 ID |
| `queries[]` | object[] | 是 | 查询列表，每个元素支持 `query_type` 与对应输入字段 |
| `top_k` | int | 是 | 每条查询返回结果数 |
| `export_format` | enum | 是 | 可选：`json`、`csv` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.task_id` | string | 批量检索任务 ID |
| `data.status` | string | 任务状态，初始值通常为 `pending` |

**请求示例**

```json
{
  "method": "POST",
  "path": "/batch-search",
  "headers": {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  },
  "body": {
    "dataset_id": 12,
    "index_id": 7,
    "queries": [
      {
        "query_type": "cell_id",
        "cell_id": "cell_000001"
      },
      {
        "query_type": "cell_id",
        "cell_id": "cell_000002"
      }
    ],
    "top_k": 10,
    "export_format": "csv"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "task_batch_001",
    "status": "pending"
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40001` | 缺少 `queries` 或查询项关键字段 |
| `40002` | 导出格式、查询类型或查询内容格式错误 |
| `40303` | 批量任务配额超限 |
| `40402` / `40403` | 数据集或索引不存在 |

### 4.3 查询任务状态

- **接口名称：** 查询任务状态

- **请求方式 + 路径：** `GET /tasks/{task_id}`

- **权限要求：** `admin` / `dev` / `user` / `readonly` / `service` / `auditor`

- **接口说明：** 轮询异步任务状态，适用于建索引、预处理、批量检索、报告导出等流程。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `task_id (Path)` | string | 是 | 任务 ID |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.task_id` | string | 任务 ID |
| `data.type` | string | 任务类型，如 `batch_search` |
| `data.progress` | int | 任务进度，范围 0-100 |
| `data.status` | string | 状态：`pending`、`running`、`done`、`failed`、`cancelled` |
| `data.result_url` | string/null | 结果地址，未完成时可为空 |

**请求示例**

```json
{
  "method": "GET",
  "path": "/tasks/task_batch_001",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "task_batch_001",
    "type": "batch_search",
    "progress": 65,
    "status": "running",
    "result_url": null
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40404` | 任务不存在 |
| `40302` | 当前用户无权查看目标任务 |

### 4.4 导出检索结果

- **接口名称：** 导出检索结果

- **请求方式 + 路径：** `GET /tasks/{task_id}/export`

- **权限要求：** `admin` / `dev` / `user` / `service`

- **接口说明：** 下载批量检索或报告导出任务的生成结果。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `task_id (Path)` | string | 是 | 任务 ID |
| `format (Query)` | string | 是 | 导出格式，例如 `csv` 或 `pdf` |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.download_url` | string | 导出文件下载地址 |

**请求示例**

```json
{
  "method": "GET",
  "path": "/tasks/task_batch_001/export?format=csv",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "download_url": "/api/v1/files/exports/task_batch_001.csv"
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40002` | 导出格式不支持 |
| `40404` | 任务不存在或导出结果尚未生成 |
| `50004` | 导出文件不存在或文件系统读取失败 |

---

## 五、可视化与指标模块（`/visualizations`、`/metrics`、`/reports`）

### 5.1 获取 UMAP/t-SNE 点位数据

- **接口名称：** 获取 UMAP/t-SNE 点位数据

- **请求方式 + 路径：** `GET /visualizations/{dataset_id}/embedding`

- **权限要求：** `admin` / `dev` / `user` / `readonly` / `auditor`

- **接口说明：** 获取指定数据集的二维降维点位，支持分页、颜色映射与视口裁剪。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `dataset_id (Path)` | int | 是 | 数据集 ID |
| `method (Query)` | enum | 是 | 可选：`umap`、`tsne` |
| `page (Query)` | int | 否 | 页码，从 1 开始 |
| `page_size (Query)` | int | 否 | 每页点位数，示例中为 5000 |
| `color_by (Query)` | string | 否 | 着色字段，如 `cell_type` |
| `bbox (Query)` | string | 否 | 视口裁剪范围，格式：`x1,y1,x2,y2` |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.points[]` | object[] | 二维点位数组 |
| `data.points[].cell_id` | string | 细胞 ID |
| `data.points[].x` / `data.points[].y` | float | 二维坐标值 |
| `data.points[].color_label` | string | 颜色映射标签 |
| `data.total` | int | 总点位数 |
| `data.legend[]` | object[] | 图例数组 |
| `data.legend[].label` | string | 标签名称 |
| `data.legend[].color` | string | 十六进制颜色值 |

**请求示例**

```json
{
  "method": "GET",
  "path": "/visualizations/12/embedding?method=umap&page=1&page_size=5000&color_by=cell_type",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "points": [
      {
        "cell_id": "cell_000001",
        "x": 0.128,
        "y": -1.205,
        "color_label": "T_cell"
      }
    ],
    "total": 2700,
    "legend": [
      {
        "label": "T_cell",
        "color": "#FF6B6B"
      }
    ]
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40002` | 降维方法、分页参数或 bbox 格式错误 |
| `40402` | 数据集不存在 |

### 5.2 获取检索结果高亮点位

- **接口名称：** 获取检索结果高亮点位

- **请求方式 + 路径：** `GET /visualizations/{query_id}/highlights`

- **权限要求：** `admin` / `dev` / `user` / `readonly` / `service` / `auditor`

- **接口说明：** 基于单次检索的 `query_id` 获取查询点和邻居点在可视化平面中的高亮坐标。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `query_id (Path)` | string | 是 | 检索查询 ID |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.query_point` | object | 查询点坐标信息 |
| `data.query_point.cell_id` | string | 查询细胞 ID |
| `data.query_point.x` / `data.query_point.y` | float | 查询点二维坐标 |
| `data.neighbor_points[]` | object[] | 命中邻居点列表 |
| `data.neighbor_points[].rank` | int | 结果排名 |
| `data.neighbor_points[].cell_id` | string | 邻居细胞 ID |
| `data.neighbor_points[].x` / `data.neighbor_points[].y` | float | 邻居点二维坐标 |
| `data.neighbor_points[].score` | float | 相似度得分 |
| `data.summary.total_neighbors` | int | 邻居总数 |
| `data.summary.avg_score` | float | 平均相似度 |

**请求示例**

```json
{
  "method": "GET",
  "path": "/visualizations/q_20260521_001/highlights",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "query_point": {
      "cell_id": "cell_000981",
      "x": 0.128,
      "y": -1.205
    },
    "neighbor_points": [
      {
        "rank": 1,
        "cell_id": "cell_018723",
        "x": 0.121,
        "y": -1.19,
        "score": 0.9841
      }
    ],
    "summary": {
      "total_neighbors": 20,
      "avg_score": 0.921
    }
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40404` | 查询结果不存在或已过期 |
| `40302` | 当前用户无权访问该查询结果 |

### 5.3 获取检索性能指标

- **接口名称：** 获取检索性能指标

- **请求方式 + 路径：** `GET /metrics/search`

- **权限要求：** `admin` / `dev` / `auditor`

- **接口说明：** 查询指定索引在一段时间窗口内的检索性能指标，包括延迟、QPS、CPU 与内存。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `index_id (Query)` | int | 是 | 索引 ID |
| `time_range (Query)` | enum | 是 | 可选：`1h`、`6h`、`24h`、`7d` |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.p50` | int | P50 延迟，单位 ms |
| `data.p95` | int | P95 延迟，单位 ms |
| `data.p99` | int | P99 延迟，单位 ms |
| `data.qps` | float | 每秒查询数 |
| `data.cpu` | float | CPU 使用率，单位 % |
| `data.memory` | float | 内存使用量，单位 MB |

**请求示例**

```json
{
  "method": "GET",
  "path": "/metrics/search?index_id=7&time_range=1h",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "p50": 120,
    "p95": 450,
    "p99": 980,
    "qps": 12.5,
    "cpu": 34.2,
    "memory": 512.8
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40002` | `time_range` 格式不合法 |
| `40301` | 当前角色无性能指标访问权限 |
| `40403` | 索引不存在 |

### 5.4 触发诊断报告生成

- **接口名称：** 触发诊断报告生成

- **请求方式 + 路径：** `POST /reports/diagnostic`

- **权限要求：** `admin` / `dev` / `auditor`

- **接口说明：** 基于查询结果生成诊断报告，完成后通过任务查询与导出接口获取 PDF。

**请求参数**

| 字段名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `Authorization (Header)` | string | 是 | 格式：`Bearer <token>` |
| `query_id` | string | 是 | 查询 ID |
| `include_umap_snapshot` | boolean | 是 | 是否将 UMAP 快照纳入报告 |

**响应字段**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `data.task_id` | string | 报告生成任务 ID |
| `data.status` | string | 任务初始状态，通常为 `pending` |

**请求示例**

```json
{
  "method": "POST",
  "path": "/reports/diagnostic",
  "headers": {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  },
  "body": {
    "query_id": "q_20260521_001",
    "include_umap_snapshot": true
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "task_report_001",
    "status": "pending"
  }
}
```

**错误码说明**

| 错误码 | 说明 |
| --- | --- |
| `40001` | 缺少 `query_id` |
| `40404` | 查询结果不存在，无法生成诊断报告 |
| `50004` | 报告生成或文件输出失败 |

---

## 六、错误码汇总

| 错误码 | 类别 | 说明 |
| --- | --- | --- |
| `0` | 成功 | 请求执行成功 |
| `40001` | 参数缺失 | 请求体、查询参数、路径参数或表单字段缺失 |
| `40002` | 参数格式错误 | 字段类型、枚举值、结构或格式不合法 |
| `40003` | 参数超限 | 分页大小、上传体积、检索参数或数量超出系统限制 |
| `40101` | 鉴权失败 | Token 缺失，或登录接口场景下账号密码错误 |
| `40102` | 鉴权失败 | Token 已过期 |
| `40103` | 鉴权失败 | Token 非法 |
| `40301` | 权限不足 | 角色权限不足，或登录接口中账号已锁定 |
| `40302` | 资源无权访问 | 用户尝试访问不属于自己的用户、数据集、任务或查询结果 |
| `40303` | 配额超限 | 上传、检索或异步任务额度超过限制 |
| `40401` | 资源不存在 | 用户不存在 |
| `40402` | 资源不存在 | 数据集不存在 |
| `40403` | 资源不存在 | 索引不存在 |
| `40404` | 资源不存在 | 任务不存在，或可追踪查询结果不存在 |
| `40901` | 业务冲突 | 用户名已存在 |
| `50001` | 服务端错误 | 系统内部未知错误 |
| `50002` | 数据库错误 | 数据库读写、事务或级联删除失败 |
| `50003` | 检索引擎错误 | 索引构建、加载、发布、查询或预处理任务触发失败 |
| `50004` | 文件系统错误 | 上传分块写入、导出、报告文件生成或读取失败 |

## 七、角色权限矩阵

> `auditor` 角色定义为“只读 + 审计日志查看”。由于本次 API 清单未单独列出审计日志接口，因此矩阵中仅保留该角色在已给定接口范围内的只读能力说明。

| 角色 | 用户管理 | 数据集管理 | 索引管理 | 检索任务 | 可视化指标 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| `admin` | 全部 | 全部 | 全部 | 全部 | 全部 | 系统最高权限 |
| `dev` | 无 | 上传/查看/删除/日志 | 创建/查看/加载 | 全部 | 全部 | 不可执行用户管理、索引发布与回滚 |
| `user` | 无 | 上传/查看/本人删除 | 仅消费已存在索引 | 单次/批量检索 | 查看 | 不可执行 `load` / `publish` / `rollback` |
| `readonly` | 无 | 列表/详情/日志（只读） | 无 | 单次检索/任务只读 | 查看 | 不允许写操作 |
| `service` | 无 | 无 | 无 | `/search`、`/batch-search`、`/tasks` | 高亮结果查询 | 用于程序化调用 |
| `auditor` | 无 | 列表/详情/日志（只读） | 指标查看 | 任务只读 | 查看/报告生成 | 额外具备审计日志查看能力（接口未在本版列出） |

## 八、补充说明

1. 所有时间字段统一使用 **ISO 8601 UTC** 格式，例如 `2026-05-21T14:00:00Z`。

2. 分页字段统一使用 `page` 与 `page_size`，其中 `page` 从 1 开始。

3. 检索、预处理、索引构建与报告导出等耗时流程均采用 **异步任务** 机制，前端应基于 `task_id` 轮询 `/tasks/{task_id}`。

4. 对于 `query_type=vector` 的单次/批量检索请求，调用方需确保向量维度与目标数据集特征维度一致；否则应返回 `40002`。

5. 所有路径中的 `{user_id}`、`{dataset_id}`、`{index_id}`、`{task_id}`、`{query_id}` 均视为服务端主键或稳定唯一标识，前端与算法链路不要自作聪明去猜生成规则，容易把自己坑进去。
