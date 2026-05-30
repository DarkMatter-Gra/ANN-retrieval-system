import { type FormEvent, useEffect, useRef, useState } from "react";
import { apiCall, downloadFile } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";
import type { TaskSnapshot } from "../types";

type ReportResult = Record<string, unknown> & {
  task_id?: string;
  status?: string;
  download_url?: string;
  json_download_url?: string;
};

const DS_KEY = "ann.frontend.datasetId";
const IDX_KEY = "ann.frontend.indexId";
const QUERY_KEY = "ann.frontend.queryId";

export function ReportsPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [report, setReport] = useState<ReportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    const form = new FormData(e.currentTarget);
    const datasetId = Number(form.get("dataset_id"));
    const indexId = Number(form.get("index_id"));
    const queryId = String(form.get("query_id") || "").trim();

    try {
      const resp = await apiCall<ReportResult>({
        baseUrl,
        token,
        path: "/reports/diagnostic",
        method: "POST",
        body: {
          dataset_id: datasetId || undefined,
          index_id: indexId || undefined,
          query_id: queryId || undefined,
          include_qc: form.get("include_qc") === "on",
          include_performance: form.get("include_performance") === "on",
          include_umap_snapshot: form.get("include_umap_snapshot") === "on",
        },
      });
      setReport(resp.data);
      if (resp.data.task_id && resp.data.status !== "done") {
        void pollReportTask(String(resp.data.task_id));
      }
      showToast("诊断报告任务已提交，可在任务监控页查看进度", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }

  async function loadReportTask(taskId: string): Promise<TaskSnapshot | null> {
    try {
      const resp = await apiCall<TaskSnapshot>({
        baseUrl,
        token,
        path: `/tasks/${taskId}`,
      });
      setReport((prev) => ({
        ...(prev ?? {}),
        task_id: taskId,
        status: resp.data.status,
        progress: resp.data.progress,
        download_url: resp.data.download_url,
        json_download_url: resp.data.json_download_url,
        result_url: resp.data.result_url,
        error_message: resp.data.error_message,
      }));
      return resp.data;
    } catch (err) {
      handleError(err);
      return null;
    }
  }

  async function pollReportTask(taskId: string) {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }

    const refresh = async () => {
      const cur = await loadReportTask(taskId);
      if (cur && (cur.status === "done" || cur.status === "failed")) {
        if (timerRef.current) {
          window.clearInterval(timerRef.current);
          timerRef.current = null;
        }
        showToast(
          cur.status === "done" ? "诊断报告已生成" : "诊断报告生成失败",
          cur.status === "done" ? "success" : "error",
        );
      }
    };

    await refresh();
    timerRef.current = window.setInterval(() => {
      void refresh();
    }, 3000);
  }

  async function handleDownload(kind: "pdf" | "json") {
    if (!report) return;
    const key = kind === "pdf" ? "download_url" : "json_download_url";
    const url = String(report[key] || "");
    if (!url) {
      showToast("当前报告没有可下载链接", "error");
      return;
    }
    try {
      await downloadFile({ baseUrl, token, urlOrPath: url });
      showToast("下载已开始", "success");
    } catch (err) {
      handleError(err);
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
                defaultValue={localStorage.getItem(DS_KEY) || ""}
                placeholder="留空则全局诊断"
              />
            </label>
            <label>
              <span>索引 ID</span>
              <input
                name="index_id"
                type="number"
                min="1"
                defaultValue={localStorage.getItem(IDX_KEY) || ""}
                placeholder="留空则跳过索引"
              />
            </label>
            <label className="full">
              <span>检索 query_id（可选）</span>
              <input
                name="query_id"
                type="text"
                defaultValue={localStorage.getItem(QUERY_KEY) || ""}
                placeholder="先在向量检索页执行一次检索，会自动带入最近 query_id"
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
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.6rem",
                gridColumn: "1 / -1",
              }}
            >
              <input
                name="include_umap_snapshot"
                type="checkbox"
                defaultChecked
                style={{ width: "auto" }}
              />
              <span>包含检索高亮快照</span>
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
              <>
                <div className="inline-actions" style={{ marginBottom: "1rem" }}>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    disabled={!report.download_url}
                    onClick={() => void handleDownload("pdf")}
                  >
                    下载 PDF
                  </button>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    disabled={!report.json_download_url}
                    onClick={() => void handleDownload("json")}
                  >
                    下载 JSON
                  </button>
                </div>
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
              </>
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
