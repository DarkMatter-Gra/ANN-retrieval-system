import { Link } from "react-router-dom";
import { useState } from "react";
import { apiCall } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";

export function ResearchPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [tuningResult, setTuningResult] = useState<any>(null);
  const [tuningLoading, setTuningLoading] = useState(false);

  const [benchmarkResult, setBenchmarkResult] = useState<any>(null);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);

  async function handleAutoTune() {
    setTuningLoading(true);
    try {
      const resp = await apiCall<any>({
        baseUrl,
        token,
        path: "/research/auto-tune",
        method: "POST",
      });
      setTuningResult(resp.data);
      showToast("调优完成", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setTuningLoading(false);
    }
  }

  async function handleBenchmark() {
    setBenchmarkLoading(true);
    try {
      const resp = await apiCall<any>({
        baseUrl,
        token,
        path: "/research/benchmark",
        method: "POST",
      });
      setBenchmarkResult(resp.data);
      showToast("基准测试完成", "success");
    } catch (err) {
      handleError(err);
    } finally {
      setBenchmarkLoading(false);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
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
        <Link to="/app/search" className="feature-card">
          <strong>批量性能测试</strong>
          <p>切换到批量模式提交检索任务，评估吞吐量和延迟</p>
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
        <article className="panel">
          <div className="panel-head">
            <h3>索引参数自动调优</h3>
            <p>基于数据集特性自动推荐最优 HNSW / IVF_PQ 参数配置。</p>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <button
              className="btn btn-primary"
              onClick={handleAutoTune}
              disabled={tuningLoading}
            >
              {tuningLoading ? "调优中…" : "开始自动调优"}
            </button>
            {tuningResult && (
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
                  {JSON.stringify(tuningResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-head">
            <h3>多算法对比基准</h3>
            <p>在同一数据集上并行评测多种 ANN 算法，生成对比报告。</p>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <button
              className="btn btn-primary"
              onClick={handleBenchmark}
              disabled={benchmarkLoading}
            >
              {benchmarkLoading ? "测试中…" : "运行基准测试"}
            </button>
            {benchmarkResult && (
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
                  {JSON.stringify(benchmarkResult, null, 2)}
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
