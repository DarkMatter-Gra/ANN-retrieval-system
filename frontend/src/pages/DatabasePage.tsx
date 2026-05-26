import { Link } from "react-router-dom";
import { useState } from "react";
import { apiCall } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";

export function DatabasePage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [versionsResult, setVersionsResult] = useState<any>(null);
  const [versionsLoading, setVersionsLoading] = useState(false);

  const [lineageResult, setLineageResult] = useState<any>(null);
  const [lineageLoading, setLineageLoading] = useState(false);

  const [tenantResult, setTenantResult] = useState<any>(null);
  const [tenantLoading, setTenantLoading] = useState(false);

  const [syncResult, setSyncResult] = useState<any>(null);
  const [syncLoading, setSyncLoading] = useState(false);

  async function handleLoadVersions() {
    setVersionsLoading(true);
    try {
      const resp = await apiCall<any>({
        baseUrl,
        token,
        path: "/research/data-versions",
      });
      setVersionsResult(resp.data);
      showToast("获取数据版本成功", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setVersionsLoading(false);
    }
  }

  async function handleLoadLineage() {
    setLineageLoading(true);
    try {
      const resp = await apiCall<any>({
        baseUrl,
        token,
        path: "/research/data-lineage",
      });
      setLineageResult(resp.data);
      showToast("获取数据沿袭成功", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setLineageLoading(false);
    }
  }

  async function handleLoadTenant() {
    setTenantLoading(true);
    try {
      const resp = await apiCall<any>({
        baseUrl,
        token,
        path: "/research/tenant-isolation",
      });
      setTenantResult(resp.data);
      showToast("获取租户隔离配置成功", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setTenantLoading(false);
    }
  }

  async function handlePublicSync() {
    setSyncLoading(true);
    try {
      const resp = await apiCall<any>({
        baseUrl,
        token,
        path: "/research/public-db-sync",
        method: "POST",
      });
      setSyncResult(resp.data);
      showToast("同步任务已启动", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setSyncLoading(false);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>数据库管理工作台</h2>
        <p>管理公共单细胞参考数据库，控制数据集权限、版本与元数据。</p>
      </div>

      <div className="feature-grid">
        <Link to="/app/datasets" className="feature-card">
          <strong>数据集管理</strong>
          <p>查看、上传和管理所有公共数据集</p>
        </Link>
        <Link to="/app/indexes" className="feature-card">
          <strong>索引管理</strong>
          <p>维护各数据集的索引版本，执行上线与回滚</p>
        </Link>
        <Link to="/app/users" className="feature-card">
          <strong>用户权限管理</strong>
          <p>管理系统用户角色与数据访问权限</p>
        </Link>
      </div>

      <div className="panel-grid">
        <article className="panel">
          <div className="panel-head">
            <h3>数据版本管理</h3>
            <p>追踪数据集来源、版本历史与更新记录，支持数据集回滚。</p>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <button
              className="btn btn-primary"
              onClick={handleLoadVersions}
              disabled={versionsLoading}
            >
              {versionsLoading ? "加载中..." : "加载版本历史"}
            </button>
            {versionsResult && (
              <div className="result-card" style={{ marginTop: "1rem" }}>
                <pre
                  style={{
                    margin: 0,
                    fontSize: "0.84rem",
                    color: "var(--text-soft)",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-all",
                  }}
                >
                  {JSON.stringify(versionsResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-head">
            <h3>数据沿袭追踪</h3>
            <p>可视化数据集从原始来源到预处理完成的全链路数据流。</p>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <button
              className="btn btn-primary"
              onClick={handleLoadLineage}
              disabled={lineageLoading}
            >
              {lineageLoading ? "加载中..." : "加载沿袭图"}
            </button>
            {lineageResult && (
              <div className="result-card" style={{ marginTop: "1rem" }}>
                <pre
                  style={{
                    margin: 0,
                    fontSize: "0.84rem",
                    color: "var(--text-soft)",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-all",
                  }}
                >
                  {JSON.stringify(lineageResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-head">
            <h3>跨租户数据隔离配置</h3>
            <p>配置多租户数据访问边界，设置精细化权限策略。</p>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <button
              className="btn btn-primary"
              onClick={handleLoadTenant}
              disabled={tenantLoading}
            >
              {tenantLoading ? "加载中..." : "查看租户策略"}
            </button>
            {tenantResult && (
              <div className="result-card" style={{ marginTop: "1rem" }}>
                <pre
                  style={{
                    margin: 0,
                    fontSize: "0.84rem",
                    color: "var(--text-soft)",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-all",
                  }}
                >
                  {JSON.stringify(tenantResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-head">
            <h3>公共数据库同步</h3>
            <p>从 GEO、ENCODE、CellxGene 等公共数据库自动同步最新数据集。</p>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <button
              className="btn btn-primary"
              onClick={handlePublicSync}
              disabled={syncLoading}
            >
              {syncLoading ? "启动中..." : "启动同步任务"}
            </button>
            {syncResult && (
              <div className="result-card" style={{ marginTop: "1rem" }}>
                <pre
                  style={{
                    margin: 0,
                    fontSize: "0.84rem",
                    color: "var(--text-soft)",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-all",
                  }}
                >
                  {JSON.stringify(syncResult, null, 2)}
                </pre>
              </div>
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
