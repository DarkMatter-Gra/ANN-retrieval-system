import { Link } from 'react-router-dom';

export function DatabasePage() {
  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">公共生物数据库管理人员</p>
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
        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>数据版本管理</h3>
            <p>追踪数据集来源、版本历史与更新记录，支持数据集回滚。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>数据版本管理需要专用版本控制 API，将在后续版本中实现。</p>
          </div>
        </article>

        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>数据沿袭追踪</h3>
            <p>可视化数据集从原始来源到预处理完成的全链路数据流。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>数据沿袭追踪依赖元数据图数据库，将在后续版本中集成。</p>
          </div>
        </article>

        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>跨租户数据隔离配置</h3>
            <p>配置多租户数据访问边界，设置精细化权限策略。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>精细化权限策略配置界面将在后续版本中实现。当前通过角色（role）字段控制访问。</p>
          </div>
        </article>

        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>公共数据库同步</h3>
            <p>从 GEO、ENCODE、CellxGene 等公共数据库自动同步最新数据集。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>公共数据库同步爬虫与格式转换管线将在后续版本中实现。</p>
          </div>
        </article>
      </div>
    </div>
  );
}
