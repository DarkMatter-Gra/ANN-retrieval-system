import { useState, useEffect } from "react";
import { apiCall } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";

type SearchMetrics = {
  index_id?: number;
  time_range?: string;
  p50?: number;
  p95?: number;
  p99?: number;
  qps?: number;
  avg_progress?: number;
  indexes_total?: number;
  indexes_loaded?: number;
};

type DashboardData = {
  qps_trend: number[];
  latency_trend: number[];
  timestamps: string[];
  status: string;
};

function latestValue(values: number[] | undefined) {
  if (!values?.length) return 0;
  return Number(values[values.length - 1] ?? 0);
}

function maxValue(values: number[] | undefined) {
  if (!values?.length) return 0;
  return Math.max(...values.map((v) => Number(v) || 0), 0);
}

function TrendBars({
  title,
  values,
  labels,
  color,
  unit,
}: {
  title: string;
  values: number[];
  labels: string[];
  color: string;
  unit: string;
}) {
  const safeValues = values.length ? values.map((v) => Number(v) || 0) : [0];
  const max = Math.max(...safeValues, 1);

  return (
    <div
      style={{
        background: "#f9f9f9",
        padding: "1rem",
        borderRadius: "4px",
      }}
    >
      <h4>{title}</h4>
      <div
        style={{
          display: "flex",
          gap: "0.35rem",
          alignItems: "flex-end",
          height: "128px",
          marginTop: "1rem",
        }}
      >
        {safeValues.map((val, i) => {
          const height = Math.max((val / max) * 100, val > 0 ? 8 : 2);
          return (
            <div
              key={i}
              style={{
                flex: 1,
                minWidth: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "flex-end",
                height: "100%",
              }}
            >
              <span
                style={{
                  fontSize: "0.72rem",
                  color: "var(--text-soft)",
                  marginBottom: "4px",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {val}
              </span>
              <div
                style={{
                  width: "100%",
                  maxWidth: "48px",
                  minHeight: "2px",
                  height: `${height}%`,
                  background: color,
                  borderRadius: "6px 6px 0 0",
                }}
                title={`${title}: ${val}${unit}`}
              />
              <span
                style={{
                  fontSize: "0.68rem",
                  marginTop: "4px",
                  color: "var(--muted)",
                  maxWidth: "64px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={labels[i] ?? "-"}
              >
                {labels[i] ?? "-"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function MetricsPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [metrics, setMetrics] = useState<SearchMetrics | null>(null);
  const [loading, setLoading] = useState(false);

  const [dashboardData, setDashboardData] = useState<DashboardData | null>(
    null,
  );
  const [loadingDashboard, setLoadingDashboard] = useState(false);

  async function loadMetrics() {
    setLoading(true);
    try {
      const resp = await apiCall<SearchMetrics>({
        baseUrl,
        token,
        path: "/metrics/search",
      });
      setMetrics(resp.data);
      showToast("指标已刷新", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }

  async function loadDashboard() {
    setLoadingDashboard(true);
    try {
      const resp = await apiCall<DashboardData>({
        baseUrl,
        token,
        path: "/ops/performance-dashboard",
      });
      setDashboardData(resp.data);
    } catch (err) {
      handleError(err);
    } finally {
      setLoadingDashboard(false);
    }
  }

  useEffect(() => {
    loadMetrics();
    loadDashboard();
  }, []);

  const qpsTrend = dashboardData?.qps_trend ?? [];
  const latencyTrend = dashboardData?.latency_trend ?? [];
  const timestamps = dashboardData?.timestamps ?? [];

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>检索性能统计</h2>
        <p>查看各索引的延迟、召回率和错误率统计数据。</p>
      </div>

      <article className="panel">
        <div className="panel-head panel-head-row">
          <div>
            <h3>搜索指标</h3>
            <p>来源：GET /metrics/search</p>
          </div>
          <div className="inline-actions">
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => void loadMetrics()}
              disabled={loading}
            >
              {loading ? "加载中…" : "刷新指标"}
            </button>
          </div>
        </div>

        {metrics ? (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>统计范围</th>
                  <th>P50 延迟 (ms)</th>
                  <th>P95 延迟 (ms)</th>
                  <th>P99 延迟 (ms)</th>
                  <th>QPS</th>
                  <th>平均进度</th>
                  <th>索引加载</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    <strong>{metrics.time_range ?? "1h"}</strong>
                    {metrics.index_id ? ` / index ${metrics.index_id}` : ""}
                  </td>
                  <td>{metrics.p50?.toFixed(2) ?? "-"}</td>
                  <td>{metrics.p95?.toFixed(2) ?? "-"}</td>
                  <td>{metrics.p99?.toFixed(2) ?? "-"}</td>
                  <td>{metrics.qps?.toFixed(4) ?? "-"}</td>
                  <td>
                    {metrics.avg_progress != null
                      ? `${metrics.avg_progress.toFixed(1)}%`
                      : "-"}
                  </td>
                  <td>
                    {metrics.indexes_loaded ?? "-"} /{" "}
                    {metrics.indexes_total ?? "-"}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        ) : (
          <div className="detail-box">
            <div className="empty-state">
              {loading ? "正在加载性能指标…" : "暂无指标数据"}
            </div>
          </div>
        )}
      </article>

      <article className="panel">
        <div className="panel-head panel-head-row">
          <div>
            <h3>实时性能监控大盘</h3>
            <p>展示检索延迟趋势图、QPS 曲线和告警阈值配置。</p>
          </div>
          <div className="inline-actions">
            <button
              className="btn btn-secondary"
              onClick={() => void loadDashboard()}
              disabled={loadingDashboard}
            >
              {loadingDashboard ? "刷新中…" : "刷新大盘"}
            </button>
          </div>
        </div>
        {dashboardData ? (
          <div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: "0.8rem",
                marginBottom: "1rem",
              }}
            >
              {[
                ["系统状态", dashboardData.status.toUpperCase()],
                ["最新 QPS", String(latestValue(qpsTrend))],
                ["峰值 QPS", String(maxValue(qpsTrend))],
                ["最新延迟", `${latestValue(latencyTrend)} ms`],
                ["最大延迟", `${maxValue(latencyTrend)} ms`],
                ["采样点", String(Math.max(qpsTrend.length, latencyTrend.length))],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="summary-box"
                  style={{ minHeight: "auto", padding: "0.75rem 0.9rem" }}
                >
                  <strong>{label}</strong>
                  <span
                    style={{
                      fontSize: "1.15rem",
                      fontWeight: 700,
                      color:
                        label === "系统状态" &&
                        dashboardData.status !== "healthy"
                          ? "var(--danger)"
                          : "var(--text)",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {value}
                  </span>
                </div>
              ))}
            </div>
            <p style={{ marginBottom: "1rem", color: "var(--text-soft)" }}>
              <strong>当前系统状态:</strong>{" "}
              <span
                style={{
                  color: dashboardData.status === "healthy" ? "green" : "red",
                }}
              >
                {dashboardData.status.toUpperCase()}
              </span>
            </p>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "1rem",
              }}
            >
              <TrendBars
                title="QPS 趋势"
                values={qpsTrend}
                labels={timestamps}
                color="#4CAF50"
                unit=""
              />
              <TrendBars
                title="延迟趋势"
                values={latencyTrend}
                labels={timestamps}
                color="#F44336"
                unit="ms"
              />
            </div>
          </div>
        ) : (
          <div className="empty-state">
            {loadingDashboard ? "正在加载实时性能大盘…" : "暂无数据"}
          </div>
        )}
      </article>

      <div className={`toast ${toast.visible ? "visible" : ""} ${toast.kind}`}>
        {toast.text}
      </div>
    </div>
  );
}
