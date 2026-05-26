import { useMemo, useState } from "react";
import { apiCall, clamp, paletteForIndex } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../lib/useToast";
import type { EmbeddingPoint, EmbeddingResponse } from "../types";

const DS_KEY = "ann.frontend.datasetId";

function computeView(embedding: EmbeddingResponse, colorBy: string) {
  const points = embedding.points ?? [];
  if (!points.length) return null;

  const sample = points[0];
  const numericKeys = Object.keys(sample).filter(
    (k) => k !== "cell_id" && typeof sample[k] === "number",
  );
  const xKey = numericKeys[0] ?? "x";
  const yKey = numericKeys[1] ?? numericKeys[0] ?? "y";

  const values = points.map((p: EmbeddingPoint) => ({
    x: Number(p[xKey]),
    y: Number(p[yKey]),
    cell_id: String(p.cell_id),
    colorValue: colorBy ? String(p[colorBy] ?? "未知") : "全部",
  }));

  const xs = values.map((v) => v.x).filter(Number.isFinite);
  const ys = values.map((v) => v.y).filter(Number.isFinite);
  const [xMin, xMax] = [Math.min(...xs), Math.max(...xs)];
  const [yMin, yMax] = [Math.min(...ys), Math.max(...ys)];
  const W = 1000;
  const H = 640;
  const P = 40;
  const scaleX = (x: number) =>
    P + ((x - xMin) / (xMax - xMin || 1)) * (W - P * 2);
  const scaleY = (y: number) =>
    H - P - ((y - yMin) / (yMax - yMin || 1)) * (H - P * 2);

  const legendValues = colorBy
    ? Array.from(new Set(values.map((v) => v.colorValue)))
    : [];
  const colorMap = new Map(legendValues.map((v, i) => [v, paletteForIndex(i)]));

  return { xKey, yKey, values, scaleX, scaleY, legendValues, colorMap };
}

export function VisualizationPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [datasetId, setDatasetId] = useState(
    () => Number(localStorage.getItem(DS_KEY) || 0) || (null as number | null),
  );
  const [method, setMethod] = useState<"umap" | "tsne">("umap");
  const [colorBy, setColorBy] = useState("");
  const [pageSize, setPageSize] = useState(2000);
  const [embedding, setEmbedding] = useState<EmbeddingResponse | null>(null);

  async function loadEmbedding() {
    if (!datasetId) {
      showToast("请输入数据集 ID", "error");
      return;
    }
    try {
      const resp = await apiCall<EmbeddingResponse>({
        baseUrl,
        token,
        path: `/visualizations/${datasetId}/embedding`,
        query: {
          method,
          page: 1,
          page_size: pageSize,
          color_by: colorBy || undefined,
        },
      });
      setEmbedding(resp.data);
      showToast(`加载完成，共 ${resp.data.total ?? 0} 个点`, "success");
    } catch (err) {
      handleError(err);
    }
  }

  const view = useMemo(
    () => (embedding ? computeView(embedding, colorBy) : null),
    [embedding, colorBy],
  );

  // 根据返回数据动态提取可作为 colorBy 的字段（非 cell_id、非数值的可枚举属性）
  const colorByOptions = useMemo(() => {
    const sample = embedding?.points?.[0];
    if (!sample) return [];
    return Object.keys(sample).filter(
      (k) => k !== "cell_id" && typeof sample[k] !== "number",
    );
  }, [embedding]);

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>UMAP / t-SNE 散点图</h2>
        <p>从后端加载降维嵌入点位并渲染交互式散点图。</p>
      </div>

      <article className="panel">
        <div className="toolbar">
          <label className="toolbar-field small">
            <span>数据集 ID</span>
            <input
              type="number"
              min="1"
              value={datasetId ?? ""}
              onChange={(e) => setDatasetId(Number(e.target.value) || null)}
            />
          </label>
          <label className="toolbar-field small">
            <span>降维方法</span>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as "umap" | "tsne")}
            >
              <option value="umap">UMAP</option>
              <option value="tsne">t-SNE</option>
            </select>
          </label>
          <label className="toolbar-field small">
            <span>颜色字段</span>
            <select
              value={colorBy}
              onChange={(e) => setColorBy(e.target.value)}
            >
              <option value="">none</option>
              {colorByOptions.length ? (
                colorByOptions.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))
              ) : (
                <>
                  <option value="cell_type">cell_type</option>
                  <option value="organ">organ</option>
                  <option value="sample_id">sample_id</option>
                </>
              )}
            </select>
          </label>
          <label className="toolbar-field small">
            <span>点数上限</span>
            <input
              type="number"
              min="1"
              max="20000"
              value={pageSize}
              onChange={(e) =>
                setPageSize(clamp(Number(e.target.value) || 2000, 1, 20000))
              }
            />
          </label>
          <button
            className="btn btn-primary"
            type="button"
            onClick={() => void loadEmbedding()}
          >
            加载点位
          </button>
        </div>

        <div className="viz-grid">
          <div className="viz-canvas-wrap">
            <svg
              id="embedding-canvas"
              viewBox="0 0 1000 640"
              preserveAspectRatio="none"
            >
              <defs>
                <linearGradient id="axisGlow" x1="0" x2="1">
                  <stop offset="0%" stopColor="#69e2c3" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#7fa8ff" stopOpacity="0.25" />
                </linearGradient>
              </defs>
              <rect x="0" y="0" width="1000" height="640" fill="transparent" />
              <line
                x1="40"
                y1="600"
                x2="960"
                y2="600"
                stroke="url(#axisGlow)"
                strokeWidth="1.2"
              />
              <line
                x1="40"
                y1="40"
                x2="40"
                y2="600"
                stroke="url(#axisGlow)"
                strokeWidth="1.2"
              />
              {view?.values.map((v) => {
                const color = view.legendValues.length
                  ? (view.colorMap.get(v.colorValue) ?? "#69e2c3")
                  : "#69e2c3";
                return (
                  <circle
                    key={v.cell_id}
                    className="viz-point"
                    cx={view.scaleX(v.x)}
                    cy={view.scaleY(v.y)}
                    r={3.5}
                    fill={color}
                    fillOpacity="0.78"
                  >
                    <title>{v.cell_id}</title>
                  </circle>
                );
              })}
              <text x="54" y="58" fill="#b9c6d8" fontSize="14">
                {view ? `${view.xKey} / ${view.yKey}` : "embedding"}
              </text>
            </svg>
          </div>

          <aside className="viz-side">
            <div className="summary-box">
              {embedding ? (
                <>
                  <div>
                    <strong>方法：</strong>
                    {embedding.method ?? method}
                  </div>
                  <div>
                    <strong>总点数：</strong>
                    {embedding.total ?? 0}
                  </div>
                  <div>
                    <strong>当前渲染：</strong>
                    {view?.values.length ?? 0}
                  </div>
                  <div>
                    <strong>颜色字段：</strong>
                    {colorBy || "none"}
                  </div>
                </>
              ) : (
                <span className="empty-state">加载后显示统计信息</span>
              )}
            </div>
            <div className="legend-box">
              {view?.legendValues.length ? (
                view.legendValues.map((v, i) => (
                  <div key={v} className="legend-item">
                    <span
                      className="legend-dot"
                      style={{ background: paletteForIndex(i) }}
                    />
                    {v}
                  </div>
                ))
              ) : (
                <span className="empty-state">暂无图例</span>
              )}
            </div>
          </aside>
        </div>
      </article>

      <div className={`toast ${toast.visible ? "visible" : ""} ${toast.kind}`}>
        {toast.text}
      </div>
    </div>
  );
}
