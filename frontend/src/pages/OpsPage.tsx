import { useState, useEffect } from "react";
import { apiCall, normalizeBaseUrl } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";

type ResourceData = {
  cpu_usage: number;
  memory_usage: number;
  gpu_usage: number;
  vector_index_memory: string;
  timestamp: string;
};

type Alert = {
  id: number;
  level: string;
  message: string;
  status: string;
  time: string;
};

type AutoScalingData = {
  enabled: boolean;
  current_instances: number;
  target_instances: number;
  min_instances: number;
  max_instances: number;
  qps_threshold: number;
};

type LogEntry = {
  timestamp: string;
  level: string;
  service: string;
  message: string;
};

export function OpsPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [healthResult, setHealthResult] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  // States for new features
  const [resourceData, setResourceData] = useState<ResourceData | null>(null);
  const [loadingResource, setLoadingResource] = useState(false);

  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [loadingAlerts, setLoadingAlerts] = useState(false);

  const [autoScaling, setAutoScaling] = useState<AutoScalingData | null>(null);
  const [loadingAutoScaling, setLoadingAutoScaling] = useState(false);
  const [scalingForm, setScalingForm] = useState({
    min_instances: 2,
    max_instances: 10,
    qps_threshold: 1000,
  });

  const [logs, setLogs] = useState<LogEntry[] | null>(null);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [logKeyword, setLogKeyword] = useState("");

  async function checkHealth() {
    setChecking(true);
    try {
      const origin = new URL(normalizeBaseUrl(baseUrl) + "/").origin;
      const resp = await fetch(`${origin}/health`);
      const text = await resp.text();
      setHealthResult(`HTTP ${resp.status} — ${text.slice(0, 200)}`);
      showToast(
        resp.ok ? "服务健康" : "服务异常",
        resp.ok ? "success" : "error",
      );
    } catch (err) {
      const msg = (err as Error).message;
      setHealthResult(`连接失败：${msg}`);
      showToast("健康检查失败", "error");
    } finally {
      setChecking(false);
    }
  }

  async function checkAuthService() {
    try {
      const resp = await apiCall<{ username: string }>({
        baseUrl,
        token,
        path: "/auth/me",
      });
      showToast(`认证服务正常，当前用户：${resp.data.username}`, "success");
    } catch (err) {
      handleError(err);
    }
  }

  async function loadResourceData() {
    setLoadingResource(true);
    try {
      const resp = await apiCall<ResourceData>({
        baseUrl,
        token,
        path: "/ops/resource-monitor",
      });
      setResourceData(resp.data);
      showToast("资源监控数据已刷新", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setLoadingResource(false);
    }
  }

  async function loadAlerts() {
    setLoadingAlerts(true);
    try {
      const resp = await apiCall<Alert[]>({
        baseUrl,
        token,
        path: "/ops/alerts",
      });
      setAlerts(resp.data);
    } catch (err) {
      handleError(err);
    } finally {
      setLoadingAlerts(false);
    }
  }

  async function resolveAlert(id: number) {
    try {
      await apiCall({
        baseUrl,
        token,
        path: `/ops/alerts/${id}/resolve`,
        method: "POST",
      });
      showToast("告警已处理", "success");
      loadAlerts();
    } catch (err) {
      handleError(err);
    }
  }

  async function loadAutoScaling() {
    setLoadingAutoScaling(true);
    try {
      const resp = await apiCall<AutoScalingData>({
        baseUrl,
        token,
        path: "/ops/auto-scaling",
      });
      setAutoScaling(resp.data);
      setScalingForm({
        min_instances: resp.data.min_instances,
        max_instances: resp.data.max_instances,
        qps_threshold: resp.data.qps_threshold,
      });
    } catch (err) {
      handleError(err);
    } finally {
      setLoadingAutoScaling(false);
    }
  }

  async function saveAutoScaling() {
    try {
      await apiCall({
        baseUrl,
        token,
        path: "/ops/auto-scaling",
        method: "POST",
        body: scalingForm,
      });
      showToast("自动扩缩容配置已保存", "success");
      loadAutoScaling();
    } catch (err) {
      handleError(err);
    }
  }

  async function loadLogs() {
    setLoadingLogs(true);
    try {
      const resp = await apiCall<LogEntry[]>({
        baseUrl,
        token,
        path: `/ops/logs?keyword=${encodeURIComponent(logKeyword)}`,
      });
      setLogs(resp.data);
    } catch (err) {
      handleError(err);
    } finally {
      setLoadingLogs(false);
    }
  }

  useEffect(() => {
    // Optionally load some initial data
    loadResourceData();
    loadAlerts();
    loadAutoScaling();
    loadLogs();
  }, []);

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>系统运维工作台</h2>
        <p>监控服务健康状态、管理系统资源与运维告警。</p>
      </div>

      <article className="panel">
        <div className="panel-head">
          <h3>服务健康检查</h3>
          <p>检查 API 服务与认证服务的可用性。</p>
        </div>
        <div className="inline-actions" style={{ marginBottom: "1rem" }}>
          <button
            className="btn btn-primary"
            type="button"
            onClick={() => void checkHealth()}
            disabled={checking}
          >
            {checking ? "检查中…" : "检查 /health"}
          </button>
          <button
            className="btn btn-secondary"
            type="button"
            onClick={() => void checkAuthService()}
          >
            检查认证服务
          </button>
        </div>
        {healthResult && (
          <div className="summary-box">
            <strong>结果：</strong>
            {healthResult}
          </div>
        )}
      </article>

      <div className="panel-grid">
        <article className="panel">
          <div className="panel-head panel-head-row">
            <div>
              <h3>实时资源监控</h3>
              <p>CPU、内存、GPU 使用率，向量索引内存占用实时大盘。</p>
            </div>
            <div className="inline-actions">
              <button
                className="btn btn-secondary"
                onClick={() => void loadResourceData()}
                disabled={loadingResource}
              >
                {loadingResource ? "刷新中…" : "刷新"}
              </button>
            </div>
          </div>
          {resourceData ? (
            <div className="summary-box">
              <p>
                <strong>CPU 使用率:</strong> {resourceData.cpu_usage}%
              </p>
              <p>
                <strong>内存 使用率:</strong> {resourceData.memory_usage}%
              </p>
              <p>
                <strong>GPU 使用率:</strong> {resourceData.gpu_usage}%
              </p>
              <p>
                <strong>向量索引内存占用:</strong>{" "}
                {resourceData.vector_index_memory}
              </p>
              <p>
                <small>更新时间: {resourceData.timestamp}</small>
              </p>
            </div>
          ) : (
            <div className="empty-state">暂无数据</div>
          )}
        </article>

        <article className="panel">
          <div className="panel-head panel-head-row">
            <div>
              <h3>服务告警管理</h3>
              <p>配置延迟、错误率、内存告警阈值，接入通知渠道。</p>
            </div>
            <div className="inline-actions">
              <button
                className="btn btn-secondary"
                onClick={() => void loadAlerts()}
                disabled={loadingAlerts}
              >
                {loadingAlerts ? "刷新中…" : "刷新"}
              </button>
            </div>
          </div>
          {alerts && alerts.length > 0 ? (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {alerts.map((a) => (
                <li
                  key={a.id}
                  style={{
                    padding: "0.5rem",
                    borderBottom: "1px solid #eee",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <strong
                      style={{
                        color: a.level === "critical" ? "red" : "orange",
                      }}
                    >
                      [{a.level.toUpperCase()}]
                    </strong>{" "}
                    {a.message}
                    <div style={{ fontSize: "0.85em", color: "#666" }}>
                      状态: {a.status} | 时间: {a.time}
                    </div>
                  </div>
                  {a.status === "active" && (
                    <button
                      className="btn btn-primary"
                      style={{ padding: "0.2rem 0.5rem", fontSize: "0.85em" }}
                      onClick={() => void resolveAlert(a.id)}
                    >
                      处理
                    </button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state">暂无告警</div>
          )}
        </article>

        <article className="panel">
          <div className="panel-head panel-head-row">
            <div>
              <h3>自动扩缩容</h3>
              <p>根据 QPS 负载自动调整索引服务实例数量。</p>
            </div>
            <div className="inline-actions">
              <button
                className="btn btn-secondary"
                onClick={() => void loadAutoScaling()}
                disabled={loadingAutoScaling}
              >
                刷新
              </button>
            </div>
          </div>
          {autoScaling ? (
            <div>
              <div style={{ marginBottom: "1rem" }}>
                <p>
                  <strong>状态:</strong>{" "}
                  {autoScaling.enabled ? "已开启" : "已关闭"}
                </p>
                <p>
                  <strong>当前实例数:</strong> {autoScaling.current_instances} /
                  目标: {autoScaling.target_instances}
                </p>
              </div>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                }}
              >
                <label>
                  最小实例数{" "}
                  <input
                    type="number"
                    value={scalingForm.min_instances}
                    onChange={(e) =>
                      setScalingForm((s) => ({
                        ...s,
                        min_instances: Number(e.target.value),
                      }))
                    }
                    style={{ width: "60px", marginLeft: "0.5rem" }}
                  />
                </label>
                <label>
                  最大实例数{" "}
                  <input
                    type="number"
                    value={scalingForm.max_instances}
                    onChange={(e) =>
                      setScalingForm((s) => ({
                        ...s,
                        max_instances: Number(e.target.value),
                      }))
                    }
                    style={{ width: "60px", marginLeft: "0.5rem" }}
                  />
                </label>
                <label>
                  QPS 扩容阈值{" "}
                  <input
                    type="number"
                    value={scalingForm.qps_threshold}
                    onChange={(e) =>
                      setScalingForm((s) => ({
                        ...s,
                        qps_threshold: Number(e.target.value),
                      }))
                    }
                    style={{ width: "80px", marginLeft: "0.5rem" }}
                  />
                </label>
                <button
                  className="btn btn-primary"
                  onClick={() => void saveAutoScaling()}
                  style={{ alignSelf: "flex-start", marginTop: "0.5rem" }}
                >
                  保存配置
                </button>
              </div>
            </div>
          ) : (
            <div className="empty-state">暂无数据</div>
          )}
        </article>

        <article className="panel">
          <div className="panel-head panel-head-row">
            <div>
              <h3>日志聚合与查询</h3>
              <p>聚合后端服务日志，支持关键词检索与时间范围过滤。</p>
            </div>
          </div>
          <div style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem" }}>
            <input
              type="text"
              placeholder="输入关键词..."
              value={logKeyword}
              onChange={(e) => setLogKeyword(e.target.value)}
              style={{ flex: 1, padding: "0.4rem" }}
            />
            <button
              className="btn btn-primary"
              onClick={() => void loadLogs()}
              disabled={loadingLogs}
            >
              查询
            </button>
          </div>
          {logs && logs.length > 0 ? (
            <div
              style={{
                background: "#f5f5f5",
                padding: "0.5rem",
                borderRadius: "4px",
                maxHeight: "200px",
                overflowY: "auto",
                fontSize: "0.85em",
                fontFamily: "monospace",
              }}
            >
              {logs.map((l, i) => (
                <div key={i} style={{ marginBottom: "0.2rem" }}>
                  <span style={{ color: "#888" }}>[{l.timestamp}]</span>{" "}
                  <strong
                    style={{
                      color:
                        l.level === "ERROR"
                          ? "red"
                          : l.level === "WARN"
                            ? "orange"
                            : "green",
                    }}
                  >
                    [{l.level}]
                  </strong>{" "}
                  <span style={{ color: "#0066cc" }}>[{l.service}]</span>:{" "}
                  {l.message}
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">无日志记录</div>
          )}
        </article>
      </div>

      <div className={`toast ${toast.visible ? "visible" : ""} ${toast.kind}`}>
        {toast.text}
      </div>
    </div>
  );
}
