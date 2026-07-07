from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.deps import get_db, require_roles
from app.models.cell_metadata import CellMetadata
from app.models.search_task import SearchTask
from app.models.dataset import ExpressionMetadata
from app.models.user import User
from app.utils.response import success

router = APIRouter(prefix="/clinical", tags=["Clinical Features"])


@router.post("/phenotype-inference")
def phenotype_inference(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "user")),
):
    """智能表型推断：基于当前可访问数据的细胞类型分布做简化统计。"""
    results = (
        db.query(CellMetadata.cell_type, func.count(CellMetadata.id).label("count"))
        .join(ExpressionMetadata, ExpressionMetadata.id == CellMetadata.dataset_id)
        .filter(ExpressionMetadata.deleted_flag.is_(False))
        .group_by(CellMetadata.cell_type)
    )
    if current_user.role != "admin":
        results = results.filter(ExpressionMetadata.owner_user_id == current_user.id)
    rows = results.all()

    total = sum(r.count for r in rows) if rows else 1

    inferred = []
    for r in rows:
        if r.cell_type:
            inferred.append(
                {
                    "trait": r.cell_type,
                    "probability": round(r.count / total, 4),
                    "confidence": "High" if r.count > 100 else "Medium",
                }
            )

    return success({"status": "completed", "inferred_phenotypes": inferred})


@router.get("/diagnostic-comparison")
def diagnostic_comparison(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "user")),
):
    """诊断案例对比：返回可访问的历史检索任务摘要。"""
    tasks = (
        db.query(SearchTask)
        .filter(SearchTask.task_type == "search")
    )
    if current_user.role != "admin":
        tasks = tasks.filter(SearchTask.owner_user_id == current_user.id)
    rows = tasks.order_by(SearchTask.id.desc()).limit(5).all()
    cases = []
    for t in rows:
        payload = t.request_payload or {}
        cases.append(
            {
                "case_id": t.task_id,
                "status": t.status,
                "result_count": payload.get("result_count", 0),
                "latency_ms": payload.get("latency_ms"),
                "note": "历史检索摘要，不包含人工诊断结论",
            }
        )
    return success(
        {"cases": cases, "summary": f"Found {len(cases)} historical diagnostic cases."}
    )


@router.get("/preprocessing-progress")
def preprocessing_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "user")),
):
    """实时预处理进度监控：查询最近的预处理任务。"""
    query = (
        db.query(SearchTask)
        .filter(SearchTask.task_type == "preprocess_dataset")
    )
    if current_user.role != "admin":
        query = query.filter(SearchTask.owner_user_id == current_user.id)
    task = query.order_by(SearchTask.id.desc()).first()
    if task:
        return success(
            {
                "task_id": task.task_id,
                "progress": task.progress,
                "status": task.status,
                "current_step": "Processing",
                "estimated_time_remaining": "N/A",
            }
        )
    return success(
        {
            "task_id": "None",
            "progress": 0,
            "status": "No tasks",
            "current_step": "None",
            "estimated_time_remaining": "0s",
        }
    )


@router.post("/differential-gene-analysis")
def differential_gene_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "user")),
):
    """差异基因分析占位：当前后端未实现分组统计，不返回伪造基因。"""
    query = db.query(ExpressionMetadata).filter(ExpressionMetadata.deleted_flag.is_(False))
    if current_user.role != "admin":
        query = query.filter(ExpressionMetadata.owner_user_id == current_user.id)
    dataset_count = query.count()
    return success(
        {
            "analysis_available": False,
            "dataset_count": dataset_count,
            "up_regulated": [],
            "down_regulated": [],
            "volcano_plot_url": "",
            "message": "当前版本未实现真实差异基因统计；请勿将此接口输出作为医学分析结论。",
        }
    )


@router.get("/api-docs-sdk")
def api_docs_sdk(_: User = Depends(require_roles("admin", "service"))):
    """5. API 文档与 SDK"""
    import urllib.request

    try:
        # 尝试获取真实的 OpenAPI 规范
        req = urllib.request.Request("http://localhost:8000/openapi.json")
        with urllib.request.urlopen(req) as response:
            openapi = response.read().decode("utf-8")
            import json

            openapi_data = json.loads(openapi)
            paths = list(openapi_data.get("paths", {}).keys())
    except Exception:
        paths = ["/docs", "/redoc", "/openapi.json"]

    return success(
        {
            "version": "1.0.0",
            "docs_url": "/docs",
            "endpoints": paths[:10],  # 只展示前10个
            "sdk_downloads": {"python": "/docs", "javascript": "/docs"},
        }
    )
