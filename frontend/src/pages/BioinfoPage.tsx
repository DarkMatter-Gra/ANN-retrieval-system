import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export function BioinfoPage() {
  const { baseUrl } = useAuth();

  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">生物信息学人员 / API 接入</p>
        <h2>API 接入工作台</h2>
        <p>通过程序化 API 执行检索与批量任务，适用于生物信息学流程自动化集成。</p>
      </div>

      <article className="panel">
        <div className="panel-head"><h3>API 接入信息</h3></div>
        <div className="detail-box">
          <div><strong>Base URL：</strong><code style={{ color: 'var(--accent)' }}>{baseUrl}</code></div>
          <div style={{ marginTop: '0.6rem' }}><strong>认证方式：</strong>Bearer Token（Header: Authorization: Bearer &lt;token&gt;）</div>
          <div style={{ marginTop: '0.6rem' }}><strong>内容类型：</strong>application/json</div>
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
          <p>GET /tasks/{'{task_id}'} — 轮询任务进度与导出结果</p>
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
              <tr><th>方法</th><th>路径</th><th>说明</th></tr>
            </thead>
            <tbody>
              {[
                ['POST', '/auth/login', '获取 access_token'],
                ['POST', '/search', '单次 ANN 检索'],
                ['POST', '/batch-search', '提交批量检索任务'],
                ['GET', '/tasks/{task_id}', '查询任务状态'],
                ['GET', '/tasks/{task_id}/export', '获取结果下载链接'],
                ['GET', '/visualizations/{dataset_id}/embedding', '获取降维嵌入点位'],
              ].map(([method, path, desc]) => (
                <tr key={path}>
                  <td><code style={{ color: 'var(--accent-3)' }}>{method}</code></td>
                  <td><code style={{ color: 'var(--accent)' }}>{path}</code></td>
                  <td>{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <article className="panel reserved-card">
        <div className="panel-head">
          <h3>API 文档与 SDK</h3>
          <p>交互式 API 文档、Python/R SDK 以及调用示例代码。</p>
        </div>
        <div className="reserved-notice">
          <span>功能预留</span>
          <p>SDK 下载和交互式 API Explorer 将在后续版本中提供。当前请参考后端 FastAPI 自动生成的 /docs 页面。</p>
        </div>
      </article>
    </div>
  );
}
