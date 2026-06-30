import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    dev = "dev"
    user = "user"
    readonly = "readonly"
    service = "service"
    auditor = "auditor"


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"
    deleted = "deleted"
    locked = "locked"


class QCStatus(str, enum.Enum):
    pending = "pending"
    passed = "passed"
    failed = "failed"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class IndexType(str, enum.Enum):
    flat = "flat"
    ivf_pq = "ivf_pq"
    hnsw = "hnsw"
    # 自研改进算法：HNSW 召回 + 精排重排（可选 fp16 向量压缩，兼顾召回率/时延/内存）
    hnsw_rerank = "hnsw_rerank"


class MetricType(str, enum.Enum):
    l2 = "l2"
    ip = "ip"
    cosine = "cosine"


class PublishStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    published = "published"


# 角色集合，避免散落字符串
WRITE_ROLES = {"admin", "dev", "user"}
READ_ROLES = {"admin", "dev", "user", "readonly", "service", "auditor"}
INDEX_OPS_ROLES = {"admin", "dev"}
ADMIN_ONLY = {"admin"}
