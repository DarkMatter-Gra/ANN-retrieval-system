import { useState } from 'react';
import { apiCall } from '../api';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../lib/useToast';

type MetricItem = {
  index_id?: number;
  index_name?: string;
  avg_latency_ms?: number;
  p99_latency_ms?: number;
  recall_at_10?: number;
  total_queries?: number;
  error_rate?: number;
  timestamp?: string;
};

export function MetricsPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [metrics, setMetrics] = useState<MetricItem[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadMetrics() {
    setLoading(true);
    try {
      const resp = await apiCall<{ list?: MetricItem[] } | MetricItem[]>({
        baseUrl, token, path: '/metrics/search',
      });
      const data = resp.data;
      const list = Array.isArray(data) ? data : (data as { list?: MetricItem[] }).list ?? [data as MetricItem];
      setMetrics(list);
      showToast('指标已刷新', 'success');
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">性能指标</p>
        <h2>检索性能统计</h2>
        <p>查看各索引的延迟、召回率和错误率统计数据。</p>
      </div>

      <article className="panel">
        <div className="panel-head panel-head-row">
          <div>
            <h3>搜索指标</h3>
            <p>来源：GET /metrics/search</p>
          </div>
          <div className="inline-actions">
            <button className="btn btn-primary" type="button" onClick={() => void loadMetrics()} disabled={loading}>
              {loading ? '加载中…' : '刷新指标'}
            </button>
          </div>
        </div>

        {metrics ? (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>索引 ID</th>
                  <th>索引名称</th>
                  <th>平均延迟 (ms)</th>
                  <th>P99 延迟 (ms)</th>
                  <th>Recall@10</th>
                  <th>总查询数</th>
                  <th>错误率</th>
                </tr>
              </thead>
              <tbody>
                {metrics.length ? metrics.map((m, i) => (
                  <tr key={m.index_id ?? i}>
                    <td><strong>{m.index_id ?? '-'}</strong></td>
                    <td>{m.index_name ?? '-'}</td>
                    <td>{m.avg_latency_ms?.toFixed(2) ?? '-'}</td>
                    <td>{m.p99_latency_ms?.toFixed(2) ?? '-'}</td>
                    <td>{m.recall_at_10 != null ? `${(m.recall_at_10 * 100).toFixed(1)}%` : '-'}</td>
                    <td>{m.total_queries ?? '-'}</td>
                    <td>{m.error_rate != null ? `${(m.error_rate * 100).toFixed(2)}%` : '-'}</td>
                  </tr>
                )) : (
                  <tr><td colSpan={7}><div className="empty-state">暂无指标数据</div></td></tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="detail-box">
            <div className="empty-state">点击"刷新指标"获取最新性能数据</div>
          </div>
        )}
      </article>

      <article className="panel reserved-card">
        <div className="panel-head">
          <h3>实时性能监控大盘</h3>
          <p>展示检索延迟趋势图、QPS 曲线和告警阈值配置。</p>
        </div>
        <div className="reserved-notice">
          <span>功能预留</span>
          <p>实时监控大盘需要 WebSocket 推送接口支持，将在后续版本中实现。</p>
        </div>
      </article>

      <div className={`toast ${toast.visible ? 'visible' : ''} ${toast.kind}`}>{toast.text}</div>
    </div>
  );
}
