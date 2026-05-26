import { type FormEvent, useState } from "react";
import { apiCall } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";

type ReportResult = Record<string, unknown>;

export function ReportsPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [report, setReport] = useState<ReportResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    const form = new FormData(e.currentTarget);
    const datasetId = Number(form.get("dataset_id"));
    const indexId = Number(form.get("index_id"));

    try {
      const resp = await apiCall<ReportResult>({
        baseUrl,
        token,
        path: "/reports/diagnostic",
        method: "POST",
        body: {
          dataset_id: datasetId || undefined,
          index_id: indexId || undefined,
          include_qc: form.get("include_qc") === "on",
          include_performance: form.get("include_performance") === "on",
        },
      });
      setReport(resp.data);
      showToast("诊断报告任务已提交，可在任务监控页查看进度", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>系统诊断报告</h2>
        <p>生成指定数据集或索引的质量诊断报告。</p>
      </div>

      <div className="detail-grid">
        <article className="panel">
          <div className="panel-head">
            <h3>生成报告</h3>
          </div>
          <form className="form-grid" onSubmit={handleSubmit}>
            <label>
              <span>数据集 ID</span>
              <input
                name="dataset_id"
                type="number"
                min="1"
                placeholder="留空则全局诊断"
              />
            </label>
            <label>
              <span>索引 ID</span>
              <input
                name="index_id"
                type="number"
                min="1"
                placeholder="留空则跳过索引"
              />
            </label>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.6rem",
                gridColumn: "1 / -1",
              }}
            >
              <input
                name="include_qc"
                type="checkbox"
                defaultChecked
                style={{ width: "auto" }}
              />
              <span>包含 QC 报告</span>
            </label>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.6rem",
                gridColumn: "1 / -1",
              }}
            >
              <input
                name="include_performance"
                type="checkbox"
                defaultChecked
                style={{ width: "auto" }}
              />
              <span>包含性能报告</span>
            </label>
            <button
              className="btn btn-primary full"
              type="submit"
              disabled={loading}
            >
              {loading ? "生成中…" : "生成诊断报告"}
            </button>
          </form>
        </article>

        <article className="panel">
          <div className="panel-head">
            <h3>报告内容</h3>
          </div>
          <div className="detail-box" style={{ minHeight: "300px" }}>
            {report ? (
              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  margin: 0,
                  fontSize: "0.85rem",
                  lineHeight: 1.6,
                }}
              >
                {JSON.stringify(report, null, 2)}
              </pre>
            ) : (
              <span className="empty-state">提交表单后报告将显示在这里</span>
            )}
          </div>
        </article>
      </div>

      <div className={`toast ${toast.visible ? "visible" : ""} ${toast.kind}`}>
        {toast.text}
      </div>
    </div>
  );
}
