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

  const qpsMax = dashboardData
    ? Math.max(...dashboardData.qps_trend, 1)
    : 1;
  const latencyMax = dashboardData
    ? Math.max(...dashboardData.latency_trend, 1)
    : 1;

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
            <p style={{ marginBottom: "1rem" }}>
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
              <div
                style={{
                  background: "#f9f9f9",
                  padding: "1rem",
                  borderRadius: "4px",
                }}
              >
                <h4>QPS 趋势</h4>
                <div
                  style={{
                    display: "flex",
                    gap: "0.2rem",
                    alignItems: "flex-end",
                    height: "100px",
                    marginTop: "1rem",
                  }}
                >
                  {dashboardData.qps_trend.map((val, i) => (
                    <div
                      key={i}
                      style={{
                        flex: 1,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                      }}
                    >
                      <div
                        style={{
                          width: "100%",
                          background: "#4CAF50",
                          height: `${(val / qpsMax) * 100}%`,
                        }}
                        title={`QPS: ${val}`}
                      ></div>
                      <span style={{ fontSize: "0.7em", marginTop: "4px" }}>
                        {dashboardData.timestamps[i] ?? "-"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              <div
                style={{
                  background: "#f9f9f9",
                  padding: "1rem",
                  borderRadius: "4px",
                }}
              >
                <h4>延迟趋势 (ms)</h4>
                <div
                  style={{
                    display: "flex",
                    gap: "0.2rem",
                    alignItems: "flex-end",
                    height: "100px",
                    marginTop: "1rem",
                  }}
                >
                  {dashboardData.latency_trend.map((val, i) => (
                    <div
                      key={i}
                      style={{
                        flex: 1,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                      }}
                    >
                      <div
                        style={{
                          width: "100%",
                          background: "#F44336",
                          height: `${(val / latencyMax) * 100}%`,
                        }}
                        title={`Latency: ${val}ms`}
                      ></div>
                      <span style={{ fontSize: "0.7em", marginTop: "4px" }}>
                        {dashboardData.timestamps[i] ?? "-"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="empty-state">暂无数据</div>
        )}
      </article>

      <div className={`toast ${toast.visible ? "visible" : ""} ${toast.kind}`}>
        {toast.text}
      </div>
    </div>
  );
}
