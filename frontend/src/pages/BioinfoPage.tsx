import { useState } from "react";
import { Link } from "react-router-dom";
import { apiCall } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";

export function BioinfoPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [apiDocs, setApiDocs] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchApiDocs = async () => {
    setLoading(true);
    try {
      const res = await apiCall<any>({
        baseUrl,
        token,
        path: "/clinical/api-docs-sdk",
        method: "GET",
      });
      setApiDocs(res.data);
      showToast("获取 API 文档与 SDK 成功", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      {toast.visible && (
        <div className={`toast toast-${toast.kind}`}>{toast.text}</div>
      )}
      <div className="page-header">
        <h2>API 接入工作台</h2>
        <p>
          通过程序化 API 执行检索与批量任务，适用于生物信息学流程自动化集成。
        </p>
      </div>

      <article className="panel">
        <div className="panel-head">
          <h3>API 接入信息</h3>
        </div>
        <div className="detail-box">
          <div>
            <strong>Base URL：</strong>
            <code style={{ color: "var(--accent)" }}>{baseUrl}</code>
          </div>
          <div style={{ marginTop: "0.6rem" }}>
            <strong>认证方式：</strong>Bearer Token（Header: Authorization:
            Bearer &lt;token&gt;）
          </div>
          <div style={{ marginTop: "0.6rem" }}>
            <strong>内容类型：</strong>application/json
          </div>
        </div>
      </article>

      <div className="feature-grid">
        <Link to="/app/search" className="feature-card">
          <strong>单次检索 API</strong>
          <p>POST /search — 执行单次 ANN 检索，返回 top-k 近邻结果</p>
        </Link>
        <Link to="/app/batch-search" className="feature-card">
          <strong>批量检索 API</strong>
          <p>POST /batch-search — 提交异步批量检索任务</p>
        </Link>
        <Link to="/app/tasks" className="feature-card">
          <strong>任务状态查询</strong>
          <p>GET /tasks/{"{task_id}"} — 轮询任务进度与导出结果</p>
        </Link>
      </div>

      <article className="panel">
        <div className="panel-head">
          <h3>关键 API 端点</h3>
          <p>适用于程序化调用的核心接口列表。</p>
        </div>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>方法</th>
                <th>路径</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["POST", "/auth/login", "获取 access_token"],
                ["POST", "/search", "单次 ANN 检索"],
                ["POST", "/batch-search", "提交批量检索任务"],
                ["GET", "/tasks/{task_id}", "查询任务状态"],
                ["GET", "/tasks/{task_id}/export", "获取结果下载链接"],
                [
                  "GET",
                  "/visualizations/{dataset_id}/embedding",
                  "获取降维嵌入点位",
                ],
              ].map(([method, path, desc]) => (
                <tr key={path}>
                  <td>
                    <code style={{ color: "var(--accent-3)" }}>{method}</code>
                  </td>
                  <td>
                    <code style={{ color: "var(--accent)" }}>{path}</code>
                  </td>
                  <td>{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <article className="panel">
        <div className="panel-head">
          <h3>API 文档与 SDK</h3>
          <p>交互式 API 文档、Python/R SDK 以及调用示例代码。</p>
        </div>
        <div className="panel-body" style={{ marginTop: "1rem" }}>
          <button
            className="btn btn-primary"
            onClick={fetchApiDocs}
            disabled={loading}
          >
            {loading ? "加载中..." : "加载最新 API 文档与 SDK"}
          </button>
          {apiDocs && (
            <div
              className="result-card"
              style={{
                marginTop: "1rem",
                padding: "1rem",
                background: "#f5f5f5",
                borderRadius: "4px",
              }}
            >
              <h4>当前版本: {apiDocs.version}</h4>
              <p>
                在线文档:{" "}
                <a href={apiDocs.docs_url} target="_blank" rel="noreferrer">
                  {apiDocs.docs_url}
                </a>
              </p>

              <h5 style={{ marginTop: "1rem" }}>新增 API 端点:</h5>
              <ul style={{ paddingLeft: "20px" }}>
                {apiDocs.endpoints.map((ep: string, i: number) => (
                  <li key={i}>
                    <code>{ep}</code>
                  </li>
                ))}
              </ul>

              <h5 style={{ marginTop: "1rem" }}>SDK 下载:</h5>
              <ul style={{ paddingLeft: "20px" }}>
                <li>
                  Python SDK:{" "}
                  <a
                    href={apiDocs.sdk_downloads.python}
                    target="_blank"
                    rel="noreferrer"
                  >
                    下载 .tar.gz
                  </a>
                </li>
                <li>
                  JavaScript SDK:{" "}
                  <a
                    href={apiDocs.sdk_downloads.javascript}
                    target="_blank"
                    rel="noreferrer"
                  >
                    下载 .tgz
                  </a>
                </li>
              </ul>
            </div>
          )}
        </div>
      </article>
    </div>
  );
}
