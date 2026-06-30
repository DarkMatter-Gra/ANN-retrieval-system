import { type FormEvent, useState } from "react";
import { apiCall } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";
import type { SearchResult } from "../types";

const DS_KEY = "ann.frontend.datasetId";
const IDX_KEY = "ann.frontend.indexId";

type AiSearchResponse = {
  question: string;
  parsed_query: Record<string, unknown>;
  answer: string;
  stats: {
    total: number;
    cell_type: Record<string, number>;
    organ: Record<string, number>;
    sample_id: Record<string, number>;
  };
  query_id?: string;
  latency_ms?: number;
  results: SearchResult[];
};

export function AiSearchPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [submitting, setSubmitting] = useState(false);
  const [data, setData] = useState<AiSearchResponse | null>(null);

  async function handleAsk(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);

    const datasetId = Number(form.get("dataset_id"));
    const indexId = Number(form.get("index_id"));
    const question = String(form.get("question") || "").trim();

    if (!datasetId || !indexId) {
      showToast("请填写数据集 ID 和索引 ID", "error");
      return;
    }
    if (!question) {
      showToast("请输入你的问题", "error");
      return;
    }

    localStorage.setItem(DS_KEY, String(datasetId));
    localStorage.setItem(IDX_KEY, String(indexId));

    setSubmitting(true);
    try {
      const resp = await apiCall<AiSearchResponse>({
        baseUrl,
        token,
        path: "/ai/search",
        method: "POST",
        body: {
          dataset_id: datasetId,
          index_id: indexId,
          question,
        },
      });
      setData(resp.data);
      showToast(`AI 检索完成，耗时 ${resp.data.latency_ms ?? "-"} ms`, "success");
    } catch (err) {
      handleError(err);
    } finally {
      setSubmitting(false);
    }
  }

  const results = data?.results ?? [];

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>AI 自然语言检索</h2>
        <p>用自然语言提问，系统自动解析检索条件并生成 AI 分析解读。</p>
      </div>

      <div className="detail-grid">
        <article className="panel">
          <div className="panel-head">
            <h3>提问</h3>
          </div>
          <form className="form-grid" onSubmit={handleAsk}>
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
            <label className="full">
              <span>你的问题</span>
              <textarea
                name="question"
                rows={3}
                placeholder="例如：找和肝细胞最相似的细胞 / 看看肝脏里的 Kupffer 细胞"
                spellCheck={false}
              />
            </label>
            <button
              className="btn btn-primary full"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "AI 分析中…" : "提问"}
            </button>
          </form>

          {data && (
            <div className="summary-box" style={{ marginTop: "1rem" }}>
              <div>
                <strong>解析条件：</strong>
                {JSON.stringify(data.parsed_query)}
              </div>
              <div>
                <strong>query_id：</strong>
                {data.query_id ?? "-"}
              </div>
              <div>
                <strong>latency_ms：</strong>
                {data.latency_ms ?? "-"}
              </div>
              <div>
                <strong>结果数：</strong>
                {data.stats?.total ?? results.length}
              </div>
            </div>
          )}
        </article>

        <div style={{ display: "grid", gap: "1.2rem" }}>
          <article className="panel">
            <div className="panel-head">
              <h3>AI 解读</h3>
            </div>
            <div className="detail-box">
              {data?.answer ? (
                <p style={{ lineHeight: 1.7 }}>{data.answer}</p>
              ) : (
                <div className="empty-state">提问后这里会显示 AI 分析</div>
              )}
            </div>
          </article>

          <article className="panel">
            <div className="panel-head">
              <h3>检索结果</h3>
            </div>
            <div className="result-list">
              {results.length ? (
                results.map((item) => (
                  <article
                    key={`${item.rank}-${item.cell_id}`}
                    className="result-card"
                  >
                    <header>
                      <div>
                        <h5>
                          #{item.rank} {item.cell_id}
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
                <div className="empty-state">提问后结果将显示在这里</div>
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
