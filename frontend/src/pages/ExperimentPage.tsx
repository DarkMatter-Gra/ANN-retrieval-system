import { useState } from "react";
import { Link } from "react-router-dom";
import { apiCall } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";

export function ExperimentPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [progressData, setProgressData] = useState<any>(null);
  const [loadingProgress, setLoadingProgress] = useState(false);

  const [degData, setDegData] = useState<any>(null);
  const [loadingDeg, setLoadingDeg] = useState(false);

  const handleFetchProgress = async () => {
    setLoadingProgress(true);
    try {
      const res = await apiCall<any>({
        baseUrl,
        token,
        path: "/clinical/preprocessing-progress",
        method: "GET",
      });
      setProgressData(res.data);
      showToast("获取进度成功", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setLoadingProgress(false);
    }
  };

  const handleFetchDeg = async () => {
    setLoadingDeg(true);
    try {
      const res = await apiCall<any>({
        baseUrl,
        token,
        path: "/clinical/differential-gene-analysis",
        method: "POST",
      });
      setDegData(res.data);
      showToast("差异基因分析完成", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setLoadingDeg(false);
    }
  };

  return (
    <div className="page-container">
      <div className={`toast ${toast.visible ? "visible" : ""} ${toast.kind}`}>
        {toast.text}
      </div>
      <div className="page-header">
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
        <Link to="/app/search" className="feature-card">
          <strong>批量样本分析</strong>
          <p>切换到批量模式，提交大规模样本检索任务</p>
        </Link>
        <Link to="/app/reports" className="feature-card">
          <strong>质控报告</strong>
          <p>查看数据集 QC 指标与预处理诊断报告</p>
        </Link>
      </div>

      <div className="panel-grid">
        <article className="panel">
          <div className="panel-head">
            <h3>实时预处理进度监控</h3>
            <p>上传数据集后，实时追踪质控、标准化、降维各处理步骤进度。</p>
          </div>
          <div className="panel-body" style={{ marginTop: "1rem" }}>
            <button
              className="btn btn-primary"
              onClick={handleFetchProgress}
              disabled={loadingProgress}
            >
              {loadingProgress ? "获取中…" : "刷新进度"}
            </button>
            {progressData && (
              <div
                className="result-card"
                style={{
                  marginTop: "1rem",
                  padding: "1rem",
                  background: "#f5f5f5",
                  borderRadius: "4px",
                }}
              >
                <h4>任务 ID: {progressData.task_id}</h4>
                <div
                  style={{
                    background: "#ddd",
                    height: "10px",
                    borderRadius: "5px",
                    marginTop: "10px",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      background: "#4caf50",
                      width: `${progressData.progress}%`,
                      height: "100%",
                    }}
                  ></div>
                </div>
                <p style={{ marginTop: "0.5rem" }}>
                  当前进度: {progressData.progress}% ({progressData.status})
                </p>
                <p>当前阶段: {progressData.current_step}</p>
                <p>预计剩余时间: {progressData.estimated_time_remaining}</p>
              </div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-head">
            <h3>差异基因分析</h3>
            <p>对检索到的邻域细胞进行差异表达基因分析（DEG）。</p>
          </div>
          <div className="panel-body" style={{ marginTop: "1rem" }}>
            <button
              className="btn btn-primary"
              onClick={handleFetchDeg}
              disabled={loadingDeg}
            >
              {loadingDeg ? "分析中…" : "运行 DEG 分析"}
            </button>
            {degData && (
              <div
                className="result-card"
                style={{
                  marginTop: "1rem",
                  padding: "1rem",
                  background: "#f5f5f5",
                  borderRadius: "4px",
                }}
              >
                <h4>分析报告 ID: {degData.analysis_id}</h4>
                <div style={{ marginTop: "0.5rem" }}>
                  <strong>上调基因 (Up-regulated):</strong>
                  <ul style={{ paddingLeft: "20px" }}>
                    {degData.up_regulated.map((g: any, i: number) => (
                      <li key={i}>
                        {g.gene} (log2FC: {g.log2fc}, p: {g.p_value})
                      </li>
                    ))}
                  </ul>
                  <strong style={{ marginTop: "0.5rem", display: "block" }}>
                    下调基因 (Down-regulated):
                  </strong>
                  <ul style={{ paddingLeft: "20px" }}>
                    {degData.down_regulated.map((g: any, i: number) => (
                      <li key={i}>
                        {g.gene} (log2FC: {g.log2fc}, p: {g.p_value})
                      </li>
                    ))}
                  </ul>
                  {degData.volcano_plot_url && (
                    <div style={{ marginTop: "1rem" }}>
                      <a
                        href={degData.volcano_plot_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        查看火山图
                      </a>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </article>
      </div>
    </div>
  );
}
