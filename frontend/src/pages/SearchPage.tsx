import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  apiCall,
  clamp,
  downloadFile,
  normalizeVectorInput,
  safeJsonParse,
  statusLabel,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";
import type { SearchResponse, TaskSnapshot } from "../types";

const DS_KEY = "ann.frontend.datasetId";
const IDX_KEY = "ann.frontend.indexId";
const QUERY_KEY = "ann.frontend.queryId";

type SearchMode = "single" | "batch";

export function SearchPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [mode, setMode] = useState<SearchMode>("single");

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>向量检索</h2>
        <p>
          单次 ANN 检索（cell_id / 向量）与异步批量检索任务，统一入口、统一参数。
        </p>
      </div>

      <div className="seg" role="tablist" aria-label="检索模式">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "single"}
          className={`seg-item${mode === "single" ? " active" : ""}`}
          onClick={() => setMode("single")}
        >
          <SegIcon kind="single" />
          单次检索
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "batch"}
          className={`seg-item${mode === "batch" ? " active" : ""}`}
          onClick={() => setMode("batch")}
        >
          <SegIcon kind="batch" />
          批量检索
        </button>
      </div>

      {mode === "single" ? (
        <SingleSearch
          baseUrl={baseUrl}
          token={token}
          showToast={showToast}
          handleError={handleError}
        />
      ) : (
        <BatchSearch
          baseUrl={baseUrl}
          token={token}
          showToast={showToast}
          handleError={handleError}
        />
      )}

      <div className={`toast ${toast.visible ? "visible" : ""} ${toast.kind}`}>
        {toast.text}
      </div>
    </div>
  );
}

type SubProps = {
  baseUrl: string;
  token: string;
  showToast: (text: string, kind?: "info" | "success" | "error") => void;
  handleError: (err: unknown) => void;
};

function SingleSearch({ baseUrl, token, showToast, handleError }: SubProps) {
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
            <input name="ef_search" type="number" min="1" placeholder="可选" />
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
  );
}

function BatchSearch({ baseUrl, token, showToast, handleError }: SubProps) {
  const [task, setTask] = useState<TaskSnapshot | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  async function loadTask(taskId: string): Promise<TaskSnapshot | null> {
    try {
      const resp = await apiCall<TaskSnapshot>({
        baseUrl,
        token,
        path: `/tasks/${taskId}`,
      });
      setTask(resp.data);
      return resp.data;
    } catch (err) {
      handleError(err);
      return null;
    }
  }

  async function pollTask(taskId: string) {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }

    const refresh = async () => {
      const cur = await loadTask(taskId);
      if (cur && (cur.status === "done" || cur.status === "failed")) {
        if (timerRef.current) {
          window.clearInterval(timerRef.current);
          timerRef.current = null;
        }
        showToast(
          cur.status === "done" ? "批量任务已完成" : "批量任务失败",
          cur.status === "done" ? "success" : "error",
        );
      }
    };

    await refresh();
    timerRef.current = window.setInterval(() => {
      void refresh();
    }, 3000);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    const form = new FormData(e.currentTarget);

    try {
      const resp = await apiCall<{ task_id: string; status: string }>({
        baseUrl,
        token,
        path: "/batch-search",
        method: "POST",
        body: {
          dataset_id: Number(form.get("dataset_id")),
          index_id: Number(form.get("index_id")),
          queries: safeJsonParse(form.get("queries"), []),
          top_k: clamp(Number(form.get("top_k") || 10), 1, 1000),
          mode: String(form.get("mode") || "ann"),
          export_format: String(form.get("export_format") || "json"),
        },
      });
      setTask({
        task_id: resp.data.task_id,
        status: resp.data.status,
        progress: 0,
        type: "batch_search",
      });
      showToast(`批量任务已提交：${resp.data.task_id}`, "success");
      void pollTask(resp.data.task_id);
    } catch (err) {
      handleError(err);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDownload(path: string, filename: string) {
    try {
      await downloadFile({ baseUrl, token, urlOrPath: path, filename });
      showToast("下载已开始", "success");
    } catch (err) {
      handleError(err);
    }
  }

  return (
    <div className="detail-grid">
      <article className="panel">
        <div className="panel-head">
          <h3>提交批量任务</h3>
        </div>
        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            <span>数据集 ID</span>
            <input
              name="dataset_id"
              type="number"
              min="1"
              defaultValue={localStorage.getItem(DS_KEY) || ""}
              required
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
            <span>导出格式</span>
            <select name="export_format" defaultValue="json">
              <option value="json">json</option>
              <option value="csv">csv</option>
            </select>
          </label>
          <label className="full">
            <span>
              queries JSON（cell_id 应来自 obs_names，例如
              AAACCTGAGCAGGTCA-1_2）
            </span>
            <textarea
              name="queries"
              rows={8}
              defaultValue={
                '[{"query_type":"cell_id","cell_id":"AAACCTGAGCAGGTCA-1_2"},{"query_type":"cell_id","cell_id":"ATAGACCAGGGTTTCT-1_10"}]'
              }
              spellCheck={false}
            />
          </label>
          <button
            className="btn btn-primary full"
            type="submit"
            disabled={submitting}
          >
            {submitting ? "提交中…" : "提交批量任务"}
          </button>
        </form>
      </article>

      <article className="panel">
        <div className="panel-head">
          <h3>任务状态</h3>
        </div>
        <div className="summary-box">
          {task ? (
            <>
              <div>
                <strong>task_id：</strong>
                {task.task_id ?? "-"}
              </div>
              <div>
                <strong>类型：</strong>
                {task.type ?? "-"}
              </div>
              <div>
                <strong>状态：</strong>
                {statusLabel(task.status)}
              </div>
              <div>
                <strong>进度：</strong>
                {task.progress ?? 0}%
              </div>
              {task.error_message && (
                <div>
                  <strong>错误：</strong>
                  <span style={{ color: "var(--danger)" }}>
                    {task.error_message}
                  </span>
                </div>
              )}
              {task.task_id && task.status === "done" && (
                <div className="inline-actions" style={{ marginTop: "0.4rem" }}>
                  <strong>下载：</strong>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() =>
                      void handleDownload(
                        `/api/v1/files/exports/${task.task_id}.jsonl`,
                        `${task.task_id}.jsonl`,
                      )
                    }
                  >
                    下载 JSONL
                  </button>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() =>
                      void handleDownload(
                        `/api/v1/files/exports/${task.task_id}.csv`,
                        `${task.task_id}.csv`,
                      )
                    }
                  >
                    下载 CSV
                  </button>
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">
              提交任务后状态将显示在这里（每 3 秒自动刷新）
            </div>
          )}
        </div>
        {task && (
          <div style={{ marginTop: "1rem" }}>
            <div className="batch-progress">
              <div
                className="batch-progress-fill"
                style={{ width: `${task.progress ?? 0}%` }}
              />
            </div>
          </div>
        )}
      </article>
    </div>
  );
}

function SegIcon({ kind }: { kind: "single" | "batch" }) {
  if (kind === "single") {
    return (
      <svg
        viewBox="0 0 24 24"
        width="16"
        height="16"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
      </svg>
    );
  }
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="3" y="4" width="8" height="8" rx="1.5" />
      <rect x="13" y="4" width="8" height="8" rx="1.5" />
      <rect x="3" y="14" width="8" height="6" rx="1.5" />
      <rect x="13" y="14" width="8" height="6" rx="1.5" />
    </svg>
  );
}
