import { useState, useEffect } from "react";
import { apiCall } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";

type MetricItem = {
  index_id?: number;
  index_name?: string;
  avg_latency_ms?: number;
  p99_latency_ms?: number;
  recall_at_10?: number;
  total_queries?: number;
  error_rate?: number;
  timestamp?: string;
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

  const [metrics, setMetrics] = useState<MetricItem[] | null>(null);
  const [loading, setLoading] = useState(false);

  const [dashboardData, setDashboardData] = useState<DashboardData | null>(
    null,
  );
  const [loadingDashboard, setLoadingDashboard] = useState(false);

  async function loadMetrics() {
    setLoading(true);
    try {
      const resp = await apiCall<{ list?: MetricItem[] } | MetricItem[]>({
        baseUrl,
        token,
        path: "/metrics/search",
      });
      const data = resp.data;
      const list = Array.isArray(data)
        ? data
        : ((data as { list?: MetricItem[] }).list ?? [data as MetricItem]);
      setMetrics(list);
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
                  <th>索引 ID</th>
                  <th>索引名称</th>
                  <th>平均延迟 (ms)</th>
                  <th>P99 延迟 (ms)</th>
                  <th>Recall@10</th>
                  <th>总查询数</th>
                  <th>错误率</th>
                </tr>
              </thead>
              <tbody>
                {metrics.length ? (
                  metrics.map((m, i) => (
                    <tr key={m.index_id ?? i}>
                      <td>
                        <strong>{m.index_id ?? "-"}</strong>
                      </td>
                      <td>{m.index_name ?? "-"}</td>
                      <td>{m.avg_latency_ms?.toFixed(2) ?? "-"}</td>
                      <td>{m.p99_latency_ms?.toFixed(2) ?? "-"}</td>
                      <td>
                        {m.recall_at_10 != null
                          ? `${(m.recall_at_10 * 100).toFixed(1)}%`
                          : "-"}
                      </td>
                      <td>{m.total_queries ?? "-"}</td>
                      <td>
                        {m.error_rate != null
                          ? `${(m.error_rate * 100).toFixed(2)}%`
                          : "-"}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7}>
                      <div className="empty-state">暂无指标数据</div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="detail-box">
            <div className="empty-state">点击"刷新指标"获取最新性能数据</div>
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
