import { useState } from "react";
import { Link } from "react-router-dom";
import { apiCall } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";

export function ClinicalPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [inferenceData, setInferenceData] = useState<any>(null);
  const [loadingInference, setLoadingInference] = useState(false);

  const [comparisonData, setComparisonData] = useState<any>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);

  const handleInference = async () => {
    setLoadingInference(true);
    try {
      const res = await apiCall<any>({
        baseUrl,
        token,
        path: "/clinical/phenotype-inference",
        method: "POST",
      });
      setInferenceData(res.data);
      showToast("表型推断成功", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setLoadingInference(false);
    }
  };

  const handleComparison = async () => {
    setLoadingComparison(true);
    try {
      const res = await apiCall<any>({
        baseUrl,
        token,
        path: "/clinical/diagnostic-comparison",
        method: "GET",
      });
      setComparisonData(res.data);
      showToast("诊断案例对比成功", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setLoadingComparison(false);
    }
  };

  return (
    <div className="page-container">
      <div className={`toast ${toast.visible ? "visible" : ""} ${toast.kind}`}>
        {toast.text}
      </div>
      <div className="page-header">
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
        <Link to="/app/search" className="feature-card">
          <strong>批量样本检索</strong>
          <p>切换到批量模式，提交多样本检索任务并异步获取结果</p>
        </Link>
      </div>

      <div className="panel-grid">
        <article className="panel">
          <div className="panel-head">
            <h3>智能表型推断</h3>
            <p>基于检索结果自动推断细胞类型与表型标签，辅助临床诊断决策。</p>
          </div>
          <div className="panel-body" style={{ marginTop: "1rem" }}>
            <button
              className="btn btn-primary"
              onClick={handleInference}
              disabled={loadingInference}
            >
              {loadingInference ? "推断中…" : "运行表型推断"}
            </button>
            {inferenceData && (
              <div
                className="result-card"
                style={{
                  marginTop: "1rem",
                  padding: "1rem",
                  background: "#f5f5f5",
                  borderRadius: "4px",
                }}
              >
                <h4>推断结果</h4>
                <ul style={{ paddingLeft: "20px", marginTop: "0.5rem" }}>
                  {inferenceData.inferred_phenotypes.map(
                    (item: any, i: number) => (
                      <li key={i}>
                        <strong>{item.trait}</strong> - 概率:{" "}
                        {(item.probability * 100).toFixed(1)}% (置信度:{" "}
                        {item.confidence})
                      </li>
                    ),
                  )}
                </ul>
              </div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-head">
            <h3>诊断案例对比</h3>
            <p>将当前样本与历史诊断案例库进行相似性对比，辅助差异诊断。</p>
          </div>
          <div className="panel-body" style={{ marginTop: "1rem" }}>
            <button
              className="btn btn-primary"
              onClick={handleComparison}
              disabled={loadingComparison}
            >
              {loadingComparison ? "对比中…" : "加载对比案例"}
            </button>
            {comparisonData && (
              <div
                className="result-card"
                style={{
                  marginTop: "1rem",
                  padding: "1rem",
                  background: "#f5f5f5",
                  borderRadius: "4px",
                }}
              >
                <h4>对比摘要</h4>
                <p>{comparisonData.summary}</p>
                <ul style={{ paddingLeft: "20px", marginTop: "0.5rem" }}>
                  {comparisonData.cases.map((item: any, i: number) => (
                    <li key={i}>
                      <strong>{item.case_id}</strong> - 相似度:{" "}
                      {(item.similarity * 100).toFixed(1)}% <br />
                      诊断: {item.diagnosis} | 治疗: {item.treatment}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </article>
      </div>
    </div>
  );
}
