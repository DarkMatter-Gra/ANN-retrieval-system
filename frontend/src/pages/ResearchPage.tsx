import { Link } from 'react-router-dom';

export function ResearchPage() {
  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">向量检索引擎研发人员</p>
        <h2>研发工作台</h2>
        <p>索引构建调试、ANN 算法参数调优、性能基准评估与可视化分析。</p>
      </div>

      <div className="feature-grid">
        <Link to="/app/indexes" className="feature-card">
          <strong>索引管理</strong>
          <p>创建 HNSW / IVF_PQ / Flat 索引，调整构建参数</p>
        </Link>
        <Link to="/app/datasets" className="feature-card">
          <strong>数据集管理</strong>
          <p>查看数据集状态、预处理日志，上传测试数据</p>
        </Link>
        <Link to="/app/search" className="feature-card">
          <strong>单次检索调试</strong>
          <p>测试不同参数（ef_search、mode、metric）对检索的影响</p>
        </Link>
        <Link to="/app/batch-search" className="feature-card">
          <strong>批量性能测试</strong>
          <p>提交批量检索任务，评估吞吐量和延迟</p>
        </Link>
        <Link to="/app/metrics" className="feature-card">
          <strong>性能指标</strong>
          <p>查看召回率、延迟分布和 QPS 统计</p>
        </Link>
        <Link to="/app/visualization" className="feature-card">
          <strong>嵌入可视化</strong>
          <p>UMAP/t-SNE 验证索引质量与数据分布</p>
        </Link>
      </div>

      <div className="panel-grid">
        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>索引参数自动调优</h3>
            <p>基于数据集特性自动推荐最优 HNSW / IVF_PQ 参数配置。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>自动调优需要贝叶斯优化后端服务，将在后续版本中集成。</p>
          </div>
        </article>

        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>多算法对比基准</h3>
            <p>在同一数据集上并行评测多种 ANN 算法，生成对比报告。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>并行评测管线依赖任务调度系统扩展，将在后续版本中实现。</p>
          </div>
        </article>
      </div>
    </div>
  );
}
