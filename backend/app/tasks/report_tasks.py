import json
import textwrap
from pathlib import Path

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ann_index import ANNIndex
from app.models.dataset import ExpressionMetadata
from app.models.search_task import SearchTask
from app.tasks.celery_app import celery_app
from app.utils.file_store import ensure_dir
from app.utils.time import utcnow_iso


@celery_app.task(bind=True, name="generate_report_task")
def generate_report_task(self, payload: dict, user_id: int):
    db = SessionLocal()
    try:
        query_id = payload.get("query_id")
        query_task = db.query(SearchTask).filter(SearchTask.task_id == query_id).first()
        if not query_task:
            raise ValueError("query_id not found")

        dataset_id = int(query_task.dataset_id)
        dataset = db.query(ExpressionMetadata).filter(ExpressionMetadata.id == dataset_id).first()
        indexes = db.query(ANNIndex).filter(ANNIndex.dataset_id == dataset_id).all()

        report = {
            "title": payload.get("title") or "ANN Search Diagnostic Report",
            "note": payload.get("note"),
            "generated_at": utcnow_iso(),
            "query": {
                "query_id": query_id,
                "index_id": query_task.index_id,
                "payload": query_task.request_payload,
                "status": query_task.status,
            },
            "dataset": {
                "id": dataset_id,
                "name": getattr(dataset, "dataset_name", None),
                "cell_count": getattr(dataset, "cell_count", 0),
                "gene_count": getattr(dataset, "gene_count", 0),
                "feature_dim": getattr(dataset, "feature_dim", 0),
                "qc_status": getattr(dataset, "qc_status", None),
            },
            "indexes": [
                {
                    "id": i.id,
                    "type": i.index_type,
                    "metric": i.metric_type,
                    "version": i.version_no,
                    "build_status": i.build_status,
                    "publish_status": i.publish_status,
                    "recall": i.recall_score,
                    "memory_mb": i.memory_cost_mb,
                }
                for i in indexes
            ],
            "operator_user_id": user_id,
            "owner_user_id": query_task.owner_user_id,
        }

        report_dir = ensure_dir(settings.report_path)
        stem = f"diagnostic_{dataset_id}_{self.request.id}"
        json_path = report_dir / f"{stem}.json"
        pdf_path = report_dir / f"{stem}.pdf"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_pdf_report(report, pdf_path)
        return {
            "json_path": str(json_path),
            "pdf_path": str(pdf_path),
            "json_download_url": f"/api/v1/files/reports/{json_path.name}",
            "download_url": f"/api/v1/files/reports/{pdf_path.name}",
        }
    finally:
        db.close()


def _write_pdf_report(report: dict, pdf_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    font_path = _pick_font_path()
    with PdfPages(pdf_path) as pdf:
        _add_summary_page(pdf, plt, report, font_path)
        _add_results_page(pdf, plt, report, font_path)
        _add_embedding_page(pdf, plt, report, font_path)
        _add_index_page(pdf, plt, report, font_path)


def _pick_font_path() -> str | None:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def _font(font_path: str | None, size: float = 10, weight: str = "normal"):
    from matplotlib.font_manager import FontProperties

    if font_path:
        return FontProperties(fname=font_path, size=size, weight=weight)
    return FontProperties(family="DejaVu Sans", size=size, weight=weight)


def _new_canvas(plt):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor("#f6f8fb")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def _draw_header(ax, title: str, subtitle: str, font_path: str | None) -> None:
    from matplotlib.patches import Rectangle

    ax.add_patch(Rectangle((0, 0.86), 1, 0.14, facecolor="#18212f", edgecolor="none"))
    ax.add_patch(Rectangle((0, 0.855), 1, 0.006, facecolor="#1aa6a6", edgecolor="none"))
    ax.text(0.07, 0.935, title, color="white", fontproperties=_font(font_path, 18, "bold"), va="top")
    ax.text(0.07, 0.895, subtitle, color="#cbd5e1", fontproperties=_font(font_path, 9.5), va="top")


def _draw_section_title(ax, x: float, y: float, title: str, font_path: str | None) -> None:
    ax.text(x, y, title, color="#18212f", fontproperties=_font(font_path, 12.5, "bold"), va="top")
    ax.plot([x, 0.93], [y - 0.012, y - 0.012], color="#d8dee9", linewidth=0.8)


def _draw_card(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    value: str,
    detail: str,
    color: str,
    font_path: str | None,
) -> None:
    from matplotlib.patches import FancyBboxPatch, Rectangle

    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            facecolor="white",
            edgecolor="#d8dee9",
            linewidth=0.8,
        )
    )
    ax.add_patch(Rectangle((x, y), 0.008, h, facecolor=color, edgecolor="none"))
    ax.text(x + 0.025, y + h - 0.026, label, color="#64748b", fontproperties=_font(font_path, 8.2), va="top")
    ax.text(x + 0.025, y + h * 0.43, value, color="#111827", fontproperties=_font(font_path, 15, "bold"), va="center")
    ax.text(x + 0.025, y + 0.014, detail, color="#64748b", fontproperties=_font(font_path, 7.5), va="bottom")


def _draw_key_value_block(ax, x: float, y: float, w: float, rows: list[tuple[str, str]], font_path: str | None) -> None:
    from matplotlib.patches import FancyBboxPatch

    row_h = 0.036
    h = row_h * len(rows) + 0.028
    ax.add_patch(
        FancyBboxPatch(
            (x, y - h),
            w,
            h,
            boxstyle="round,pad=0.008,rounding_size=0.01",
            facecolor="white",
            edgecolor="#d8dee9",
            linewidth=0.8,
        )
    )
    for idx, (label, value) in enumerate(rows):
        yy = y - 0.023 - idx * row_h
        if idx:
            ax.plot([x + 0.015, x + w - 0.015], [yy + 0.012, yy + 0.012], color="#eef2f7", linewidth=0.8)
        ax.text(x + 0.022, yy, label, color="#64748b", fontproperties=_font(font_path, 8.5), va="top")
        ax.text(x + 0.25, yy, str(value), color="#111827", fontproperties=_font(font_path, 8.5), va="top")


def _style_table(table, font_path: str | None, header_color: str = "#18212f") -> None:
    table.auto_set_font_size(False)
    table.set_fontsize(8.2)
    for (row, _col), cell in table.get_celld().items():
        cell.get_text().set_fontproperties(_font(font_path, 8.2, "bold" if row == 0 else "normal"))
        cell.set_edgecolor("#d8dee9")
        cell.set_linewidth(0.55)
        if row == 0:
            cell.set_facecolor(header_color)
            cell.get_text().set_color("white")
        else:
            cell.set_facecolor("#ffffff" if row % 2 else "#f8fafc")
            cell.get_text().set_color("#111827")


def _add_summary_page(pdf, plt, report: dict, font_path: str | None) -> None:
    fig, ax = _new_canvas(plt)
    dataset = report.get("dataset") or {}
    query = report.get("query") or {}
    payload = query.get("payload") or {}
    title = str(report.get("title") or "ANN Search Diagnostic Report")
    _draw_header(ax, "ANN Search Diagnostic Report", title, font_path)

    _draw_section_title(ax, 0.07, 0.81, "Overview", font_path)
    cards = [
        ("Dataset", str(dataset.get("name") or "-"), f"ID {dataset.get('id')}", "#1aa6a6"),
        ("Cells", _format_number(dataset.get("cell_count")), f"{_format_number(dataset.get('gene_count'))} genes", "#3b82f6"),
        ("Feature Dim", str(dataset.get("feature_dim") or "-"), f"QC {dataset.get('qc_status')}", "#f59e0b"),
        ("Latency", f"{payload.get('latency_ms', '-')} ms", f"{payload.get('mode_used') or payload.get('mode')} mode", "#10b981"),
    ]
    for idx, card in enumerate(cards):
        x = 0.07 + (idx % 2) * 0.435
        y = 0.68 - (idx // 2) * 0.13
        _draw_card(ax, x, y, 0.39, 0.105, *card, font_path)

    _draw_section_title(ax, 0.07, 0.48, "Query Metadata", font_path)
    query_rows = [
        ("Query ID", query.get("query_id")),
        ("Index ID", query.get("index_id")),
        ("Query Type", payload.get("query_type")),
        ("Query Cell", payload.get("cell_id")),
        ("Top K", payload.get("top_k")),
        ("Metric", payload.get("metric")),
        ("Filters", json.dumps(payload.get("filters") or {}, ensure_ascii=False)),
        ("Generated At", report.get("generated_at")),
    ]
    _draw_key_value_block(ax, 0.07, 0.435, 0.86, [(k, _clip(v, 88)) for k, v in query_rows], font_path)

    if report.get("note"):
        _draw_section_title(ax, 0.07, 0.12, "Note", font_path)
        ax.text(0.07, 0.085, _clip(report["note"], 180), color="#334155", fontproperties=_font(font_path, 9), va="top")

    pdf.savefig(fig)
    plt.close(fig)


def _add_results_page(pdf, plt, report: dict, font_path: str | None) -> None:
    fig, ax = _new_canvas(plt)
    _draw_header(ax, "Search Results", "Top nearest cells returned by the selected ANN index", font_path)
    _draw_section_title(ax, 0.07, 0.81, "Top-K Result Table", font_path)

    payload = ((report.get("query") or {}).get("payload") or {})
    results = payload.get("results") or []
    rows = [
        [
            item.get("rank"),
            _clip(item.get("cell_id"), 24),
            _clip(item.get("cell_type"), 18),
            _format_float(item.get("distance")),
            _format_float(item.get("score")),
            _clip(item.get("organ"), 23),
        ]
        for item in results[:12]
    ]
    if not rows:
        rows = [["-", "No stored search result", "-", "-", "-", "-"]]
    table = ax.table(
        cellText=rows,
        colLabels=["Rank", "Cell ID", "Cell Type", "Distance", "Score", "Organ"],
        cellLoc="left",
        colLoc="left",
        bbox=[0.07, 0.30, 0.86, 0.46],
        colWidths=[0.07, 0.28, 0.16, 0.13, 0.12, 0.24],
    )
    _style_table(table, font_path)

    if results:
        first = results[0]
        _draw_section_title(ax, 0.07, 0.23, "Nearest Cell", font_path)
        _draw_key_value_block(
            ax,
            0.07,
            0.19,
            0.86,
            [
                ("Cell ID", _clip(first.get("cell_id"), 90)),
                ("Cell Type", first.get("cell_type")),
                ("Sample ID", _clip(first.get("sample_id"), 90)),
                ("Distance / Score", f"{_format_float(first.get('distance'))} / {_format_float(first.get('score'))}"),
            ],
            font_path,
        )

    pdf.savefig(fig)
    plt.close(fig)


def _add_embedding_page(pdf, plt, report: dict, font_path: str | None) -> None:
    fig, ax = _new_canvas(plt)
    _draw_header(ax, "UMAP Highlight Snapshot", "Query cell and returned neighbors projected in embedding space", font_path)

    payload = ((report.get("query") or {}).get("payload") or {})
    highlight = payload.get("highlight_points") or {}
    query = highlight.get("query")
    neighbors = highlight.get("neighbors") or []

    plot_ax = fig.add_axes([0.11, 0.22, 0.78, 0.52])
    plot_ax.set_facecolor("#ffffff")
    for spine in plot_ax.spines.values():
        spine.set_color("#d8dee9")
    plot_ax.grid(color="#e5e7eb", linewidth=0.8, alpha=0.7)

    points = [n.get("point") for n in neighbors if n.get("point")]
    if points:
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        colors = ["#1aa6a6" if i == 0 else "#3b82f6" for i in range(len(points))]
        sizes = [95 if i == 0 else 46 for i in range(len(points))]
        plot_ax.scatter(xs, ys, s=sizes, c=colors, edgecolors="white", linewidths=0.9, zorder=3)
        for idx, item in enumerate(neighbors[:5]):
            point = item.get("point")
            if not point:
                continue
            plot_ax.annotate(
                str(item.get("cell_id", ""))[:18],
                (float(point[0]), float(point[1])),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7,
                fontproperties=_font(font_path, 7),
                color="#334155",
            )
        if query:
            plot_ax.scatter([float(query[0])], [float(query[1])], s=150, c="#f59e0b", marker="*", edgecolors="#111827", linewidths=0.5, zorder=4)
        _pad_plot_limits(plot_ax, xs, ys)
    else:
        plot_ax.text(0.5, 0.5, "No embedding highlight data", ha="center", va="center", transform=plot_ax.transAxes, fontproperties=_font(font_path, 11), color="#64748b")

    plot_ax.set_xlabel("UMAP 1", fontproperties=_font(font_path, 9), color="#334155")
    plot_ax.set_ylabel("UMAP 2", fontproperties=_font(font_path, 9), color="#334155")
    plot_ax.tick_params(axis="both", labelsize=8, colors="#64748b")

    _draw_section_title(ax, 0.07, 0.16, "Interpretation", font_path)
    ax.text(
        0.07,
        0.12,
        "The highlighted points show where the query cell and returned neighbors fall in the low-dimensional embedding. "
        "A compact cluster indicates that the nearest-neighbor search is consistent with the visualization space.",
        color="#334155",
        fontproperties=_font(font_path, 9),
        va="top",
        wrap=True,
    )

    pdf.savefig(fig)
    plt.close(fig)


def _add_index_page(pdf, plt, report: dict, font_path: str | None) -> None:
    fig, ax = _new_canvas(plt)
    _draw_header(ax, "Index Summary", "ANN index configuration and runtime metadata", font_path)
    _draw_section_title(ax, 0.07, 0.81, "Built Indexes", font_path)

    indexes = report.get("indexes") or []
    rows = [
        [
            item.get("id"),
            item.get("type"),
            item.get("metric"),
            item.get("version"),
            item.get("build_status"),
            item.get("publish_status"),
            _format_float(item.get("recall")),
            _format_float(item.get("memory_mb")),
        ]
        for item in indexes
    ]
    if not rows:
        rows = [["-", "-", "-", "-", "-", "-", "-", "-"]]

    table = ax.table(
        cellText=rows,
        colLabels=["ID", "Type", "Metric", "Ver", "Build", "Publish", "Recall", "Memory MB"],
        cellLoc="left",
        colLoc="left",
        bbox=[0.07, 0.58, 0.86, 0.18],
        colWidths=[0.06, 0.14, 0.1, 0.08, 0.15, 0.15, 0.14, 0.18],
    )
    _style_table(table, font_path)

    payload = ((report.get("query") or {}).get("payload") or {})
    _draw_section_title(ax, 0.07, 0.49, "Execution Summary", font_path)
    _draw_key_value_block(
        ax,
        0.07,
        0.45,
        0.86,
        [
            ("Mode Used", payload.get("mode_used") or payload.get("mode")),
            ("Result Count", payload.get("result_count")),
            ("Latency", f"{payload.get('latency_ms')} ms"),
            ("Operator User ID", report.get("operator_user_id")),
        ],
        font_path,
    )

    ax.text(
        0.07,
        0.17,
        "Generated by ANN Retrieval System. Runtime artifacts include the JSON report, PDF report, exported result files, "
        "and local index files; these artifacts are normally excluded from Git.",
        color="#64748b",
        fontproperties=_font(font_path, 8.5),
        va="top",
        wrap=True,
    )

    pdf.savefig(fig)
    plt.close(fig)


def _pad_plot_limits(ax, xs: list[float], ys: list[float]) -> None:
    if not xs or not ys:
        return
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    x_pad = max((x_max - x_min) * 0.18, 0.05)
    y_pad = max((y_max - y_min) * 0.18, 0.05)
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)


def _format_number(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "-"


def _format_float(value) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "-"


def _clip(value, limit: int) -> str:
    text = "" if value is None else str(value)
    text = textwrap.shorten(text, width=limit, placeholder="...")
    return text
