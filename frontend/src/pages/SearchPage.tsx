import { type FormEvent, useState } from "react";
import { apiCall, clamp, normalizeVectorInput, safeJsonParse } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";
import type { SearchResponse } from "../types";

const DS_KEY = "ann.frontend.datasetId";
const IDX_KEY = "ann.frontend.indexId";
const QUERY_KEY = "ann.frontend.queryId";

export function SearchPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [results, setResults] = useState<SearchResponse | null>(null);
  const [highlights, setHighlights] = useState<{
    query_id?: string;
    neighbors?: { cell_id: string; point: number[] }[];
  } | null>(null);
  const [highlightQueryId, setHighlightQueryId] = useState(
    () => localStorage.getItem(QUERY_KEY) || "",
  );
  const [submitting, setSubmitting] = useState(false);
  const [queryType, setQueryType] = useState<"cell_id" | "vector">("cell_id");

  async function handleSearch(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const qt = String(form.get("query_type") || "cell_id");

    // 入参校验：index_id 必填；dataset_id 可选（联合索引下允许跨数据集查询）
    const datasetIdRaw = String(form.get("dataset_id") || "").trim();
    const datasetId = datasetIdRaw ? Number(datasetIdRaw) : undefined;
    const indexId = Number(form.get("index_id"));
    if (!indexId) {
      showToast("请填写索引 ID", "error");
      return;
    }

    if (qt === "cell_id") {
      const cellId = String(form.get("cell_id") || "").trim();
      if (!cellId) {
        showToast(
          "查询类型为 cell_id 时必须填写 cell_id（来自数据集 obs_names）",
          "error",
        );
        return;
      }
    } else {
      let vec: number[];
      try {
        vec = normalizeVectorInput(form.get("vector"));
      } catch (err) {
        showToast((err as Error).message || "向量格式错误", "error");
        return;
      }
      if (!vec.length || vec.some((n) => !Number.isFinite(n))) {
        showToast("向量不能为空且必须为数值", "error");
        return;
      }
    }

    setSubmitting(true);
    const payload: Record<string, unknown> = {
      index_id: indexId,
      query_type: qt,
      top_k: clamp(Number(form.get("top_k") || 10), 1, 1000),
      mode: String(form.get("mode") || "ann"),
      metric: String(form.get("metric") || "l2"),
      filters: safeJsonParse(form.get("filters"), {}),
    };
    if (datasetId) payload.dataset_id = datasetId;

    // 跨数据集查询：source_dataset_id 指定 cell_id 解析所在数据集；dataset_ids 限制候选数据集
    const sourceDsRaw = String(form.get("source_dataset_id") || "").trim();
    if (sourceDsRaw) payload.source_dataset_id = Number(sourceDsRaw);
    const dsIdsRaw = String(form.get("dataset_ids") || "").trim();
    if (dsIdsRaw) {
      const ids = dsIdsRaw
        .split(/[,，\s]+/)
        .map((s) => Number(s.trim()))
        .filter((n) => Number.isFinite(n) && n > 0);
      if (ids.length > 0) payload.dataset_ids = ids;
    }

    const efSearch = String(form.get("ef_search") || "").trim();
    if (efSearch) payload.ef_search = Number(efSearch);

    if (qt === "cell_id") {
      payload.cell_id = String(form.get("cell_id") || "").trim();
    } else {
      payload.vector = normalizeVectorInput(form.get("vector"));
    }

    try {
      const resp = await apiCall<SearchResponse>({
        baseUrl,
        token,
        path: "/search",
        method: "POST",
        body: payload,
      });
      setResults(resp.data);
      if (resp.data.query_id) {
        setHighlightQueryId(resp.data.query_id);
        localStorage.setItem(QUERY_KEY, resp.data.query_id);
      }
      showToast(`检索完成，耗时 ${resp.data.latency_ms ?? "-"} ms`, "success");
    } catch (err) {
      handleError(err);
    } finally {
      setSubmitting(false);
    }
  }

  async function loadHighlights() {
    if (!highlightQueryId) {
      showToast("请输入 query_id", "error");
      return;
    }
    try {
      const resp = await apiCall<{
        query_id: string;
        neighbors: { cell_id: string; point: number[] }[];
      }>({
        baseUrl,
        token,
        path: `/visualizations/highlights/${highlightQueryId}`,
      });
      setHighlights(resp.data);
      showToast("高亮数据已加载", "success");
    } catch (err) {
      handleError(err);
    }
  }

  const searchList = results?.results ?? [];

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>单次 ANN 检索</h2>
        <p>支持 cell_id 查询和向量查询，可加载检索高亮邻域。</p>
      </div>

      <div className="detail-grid">
        <article className="panel">
          <div className="panel-head">
            <h3>检索参数</h3>
          </div>
          <form className="form-grid" onSubmit={handleSearch}>
            <label>
              <span>数据集 ID</span>
              <input
                name="dataset_id"
                type="number"
                min="1"
                defaultValue={localStorage.getItem(DS_KEY) || ""}
                placeholder="联合索引下可省略"
              />
            </label>
            <label>
              <span>索引 ID</span>
              <input
                name="index_id"
                type="number"
                min="1"
                defaultValue={localStorage.getItem(IDX_KEY) || ""}
                required
              />
            </label>
            <label>
              <span>source_dataset_id（跨库 cell_id 解析）</span>
              <input
                name="source_dataset_id"
                type="number"
                min="1"
                placeholder="可选；指定 cell_id 所在数据集"
              />
            </label>
            <label>
              <span>过滤候选数据集 IDs</span>
              <input
                name="dataset_ids"
                type="text"
                placeholder="如 1,2；可选，限定结果来源数据集"
              />
            </label>
            <label>
              <span>查询类型</span>
              <select
                name="query_type"
                value={queryType}
                onChange={(e) =>
                  setQueryType(e.target.value as "cell_id" | "vector")
                }
              >
                <option value="cell_id">cell_id</option>
                <option value="vector">vector</option>
              </select>
            </label>
            <label>
              <span>cell_id</span>
              <input
                name="cell_id"
                type="text"
                placeholder="如 AAACCTGAGCAGGTCA-1_2（来自 obs_names）"
                disabled={queryType !== "cell_id"}
              />
            </label>
            <label className="full">
              <span>向量（逗号分隔）</span>
              <textarea
                name="vector"
                rows={3}
                placeholder="1.0, 2.0, 3.0"
                spellCheck={false}
                disabled={queryType !== "vector"}
              />
            </label>
            <label>
              <span>Top K</span>
              <input
                name="top_k"
                type="number"
                min="1"
                max="1000"
                defaultValue={10}
              />
            </label>
            <label>
              <span>模式</span>
              <select name="mode" defaultValue="ann">
                <option value="ann">ann</option>
                <option value="exact">exact</option>
              </select>
            </label>
            <label>
              <span>度量</span>
              <select name="metric" defaultValue="l2">
                <option value="l2">l2</option>
                <option value="cosine">cosine</option>
                <option value="ip">ip</option>
              </select>
            </label>
            <label>
              <span>ef_search</span>
              <input
                name="ef_search"
                type="number"
                min="1"
                placeholder="可选"
              />
            </label>
            <label className="full">
              <span>filters JSON</span>
              <textarea
                name="filters"
                rows={3}
                defaultValue="{}"
                spellCheck={false}
              />
            </label>
            <button
              className="btn btn-primary full"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "检索中…" : "执行检索"}
            </button>
          </form>

          {results && (
            <div className="summary-box" style={{ marginTop: "1rem" }}>
              <div>
                <strong>query_id：</strong>
                {results.query_id ?? "-"}
              </div>
              <div>
                <strong>latency_ms：</strong>
                {results.latency_ms ?? "-"}
              </div>
              <div>
                <strong>recall_estimate：</strong>
                {results.recall_estimate ?? "-"}
              </div>
              <div>
                <strong>结果数：</strong>
                {searchList.length}
              </div>
            </div>
          )}
        </article>

        <div style={{ display: "grid", gap: "1.2rem" }}>
          <article className="panel">
            <div className="panel-head">
              <h3>检索结果</h3>
            </div>
            <div className="result-list">
              {searchList.length ? (
                searchList.map((item) => (
                  <article
                    key={`${item.rank}-${item.source_dataset_id ?? "x"}-${item.cell_id}`}
                    className="result-card"
                  >
                    <header>
                      <div>
                        <h5>
                          #{item.rank} {item.cell_id}
                          {item.source_dataset_id != null && (
                            <span
                              className="muted"
                              style={{ marginLeft: "0.5rem", fontSize: "0.8rem" }}
                            >
                              [ds={item.source_dataset_id}]
                            </span>
                          )}
                        </h5>
                        <p>
                          {item.cell_type ?? "-"} | {item.organ ?? "-"} |{" "}
                          {item.sample_id ?? "-"}
                        </p>
                      </div>
                      <div className="result-metrics">
                        <div>distance：{item.distance.toFixed(6)}</div>
                        <div>score：{item.score.toFixed(6)}</div>
                      </div>
                    </header>
                  </article>
                ))
              ) : (
                <div className="empty-state">执行检索后结果将显示在这里</div>
              )}
            </div>
          </article>

          <article className="panel">
            <div className="panel-head">
              <h3>检索高亮</h3>
            </div>
            <div className="detail-box">
              <div
                style={{
                  display: "flex",
                  gap: "0.6rem",
                  marginBottom: "0.8rem",
                }}
              >
                <input
                  type="text"
                  value={highlightQueryId}
                  onChange={(e) => setHighlightQueryId(e.target.value)}
                  placeholder="query_id"
                  style={{ flex: 1 }}
                />
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={() => void loadHighlights()}
                >
                  加载高亮
                </button>
              </div>
              {highlights ? (
                <>
                  <div>
                    <strong>query_id：</strong>
                    {highlights.query_id ?? "-"}
                  </div>
                  <div style={{ marginTop: "0.6rem" }}>
                    <strong>
                      邻域点（{highlights.neighbors?.length ?? 0} 个）
                    </strong>
                    {highlights.neighbors?.slice(0, 5).map((n) => (
                      <div
                        key={n.cell_id}
                        className="muted"
                        style={{ fontSize: "0.85rem" }}
                      >
                        {n.cell_id}
                      </div>
                    ))}
                    {(highlights.neighbors?.length ?? 0) > 5 && (
                      <div className="muted">…更多</div>
                    )}
                  </div>
                </>
              ) : (
                <div className="empty-state">检索后可加载高亮邻域点位</div>
              )}
            </div>
          </article>
        </div>
      </div>

      <div className={`toast ${toast.visible ? "visible" : ""} ${toast.kind}`}>
        {toast.text}
      </div>
    </div>
  );
}
