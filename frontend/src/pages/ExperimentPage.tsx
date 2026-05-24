import { Link } from 'react-router-dom';

export function ExperimentPage() {
  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">基础医学实验人员</p>
        <h2>实验分析工作台</h2>
        <p>单细胞数据上传、质控监控、预处理追踪与表型检索分析。</p>
      </div>

      <div className="feature-grid">
        <Link to="/app/datasets" className="feature-card">
          <strong>数据上传与管理</strong>
          <p>上传 h5ad / mtx 数据集，查看质控状态与预处理日志</p>
        </Link>
        <Link to="/app/search" className="feature-card">
          <strong>表型检索</strong>
          <p>以实验样本细胞为查询，检索参考数据库中的相似细胞</p>
        </Link>
        <Link to="/app/visualization" className="feature-card">
          <strong>细胞聚类可视化</strong>
          <p>UMAP/t-SNE 散点图辅助分析细胞亚群分布</p>
        </Link>
        <Link to="/app/batch-search" className="feature-card">
          <strong>批量样本分析</strong>
          <p>提交大规模样本批量检索任务</p>
        </Link>
        <Link to="/app/reports" className="feature-card">
          <strong>质控报告</strong>
          <p>查看数据集 QC 指标与预处理诊断报告</p>
        </Link>
      </div>

      <div className="panel-grid">
        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>实时预处理进度监控</h3>
            <p>上传数据集后，实时追踪质控、标准化、降维各处理步骤进度。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>实时进度推送需要 WebSocket 接口，将在后续版本中实现。当前可通过"日志"按钮查看步骤记录。</p>
          </div>
        </article>

        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>差异基因分析</h3>
            <p>对检索到的邻域细胞进行差异表达基因分析（DEG）。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>DEG 分析需要后端生物信息学计算管道，将在后续版本中集成。</p>
          </div>
        </article>
      </div>
    </div>
  );
}
