import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.ann_index import ANNIndex
from app.models.search_task import SearchTask


_TIME_RANGE_MAP = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


class MetricsService:
    def __init__(self, db: Session):
        self.db = db

    def search_metrics(
        self,
        index_id: int | None = None,
        time_range: str = "1h",
    ) -> dict:
        delta = _TIME_RANGE_MAP.get(time_range, _TIME_RANGE_MAP["1h"])
        since = datetime.now(timezone.utc) - delta

        query = (
            self.db.query(SearchTask)
            .filter(SearchTask.task_type.in_(["batch_search", "search"]))
            .filter(SearchTask.created_at >= since)
        )
        if index_id is not None:
            query = query.filter(SearchTask.index_id == index_id)
        tasks = query.order_by(SearchTask.id.desc()).limit(2000).all()

        progresses = [t.progress for t in tasks if t.progress]
        latencies: list[float] = []
        for t in tasks:
            payload = t.request_payload or {}
            if isinstance(payload, dict) and isinstance(
                payload.get("latency_ms"), (int, float)
            ):
                latencies.append(float(payload["latency_ms"]))

        def percentile(data: list[float], p: float) -> float:
            if not data:
                return 0.0
            data = sorted(data)
            k = max(0, min(len(data) - 1, int(round((p / 100.0) * (len(data) - 1)))))
            return float(data[k])

        seconds = max(delta.total_seconds(), 1.0)
        index_count = self.db.query(ANNIndex).count()
        loaded_count = (
            self.db.query(ANNIndex).filter(ANNIndex.is_loaded.is_(True)).count()
        )

        return {
            "index_id": index_id,
            "time_range": time_range,
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "qps": round(len(tasks) / seconds, 4) if tasks else 0.0,
            "avg_progress": round(statistics.mean(progresses), 2)
            if progresses
            else 0.0,
            "indexes_total": index_count,
            "indexes_loaded": loaded_count,
        }
