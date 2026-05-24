import { Link } from 'react-router-dom';

export function ClinicalPage() {
  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">临床医学诊断人员</p>
        <h2>临床诊断工作台</h2>
        <p>基于单细胞基因组数据的近似最近邻检索辅助临床表型分析与诊断参考。</p>
      </div>

      <div className="feature-grid">
        <Link to="/app/search" className="feature-card">
          <strong>相似细胞检索</strong>
          <p>输入 cell_id 或表达向量，检索表型相似的参考细胞</p>
        </Link>
        <Link to="/app/visualization" className="feature-card">
          <strong>细胞分布可视化</strong>
          <p>UMAP 散点图查看目标细胞在数据集中的分布位置</p>
        </Link>
        <Link to="/app/datasets" className="feature-card">
          <strong>数据集浏览</strong>
          <p>查看可用的单细胞数据集及其质控状态</p>
        </Link>
        <Link to="/app/reports" className="feature-card">
          <strong>诊断报告</strong>
          <p>生成数据质量与检索结果诊断报告</p>
        </Link>
        <Link to="/app/batch-search" className="feature-card">
          <strong>批量样本检索</strong>
          <p>提交多样本批量检索任务，异步获取结果</p>
        </Link>
      </div>

      <div className="panel-grid">
        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>智能表型推断</h3>
            <p>基于检索结果自动推断细胞类型与表型标签，辅助临床诊断决策。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>表型推断模型接口暂未接入，将在后续版本中集成机器学习推断服务。</p>
          </div>
        </article>

        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>诊断案例对比</h3>
            <p>将当前样本与历史诊断案例库进行相似性对比，辅助差异诊断。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>案例库对比功能依赖历史诊断数据库，将在后续版本中实现。</p>
          </div>
        </article>
      </div>
    </div>
  );
}
