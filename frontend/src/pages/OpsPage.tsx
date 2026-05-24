import { useState } from 'react';
import { apiCall, normalizeBaseUrl } from '../api';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../lib/useToast';

export function OpsPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [healthResult, setHealthResult] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  async function checkHealth() {
    setChecking(true);
    try {
      const origin = new URL(normalizeBaseUrl(baseUrl) + '/').origin;
      const resp = await fetch(`${origin}/health`);
      const text = await resp.text();
      setHealthResult(`HTTP ${resp.status} — ${text.slice(0, 200)}`);
      showToast(resp.ok ? '服务健康' : '服务异常', resp.ok ? 'success' : 'error');
    } catch (err) {
      const msg = (err as Error).message;
      setHealthResult(`连接失败：${msg}`);
      showToast('健康检查失败', 'error');
    } finally {
      setChecking(false);
    }
  }

  async function checkAuthService() {
    try {
      const resp = await apiCall<{ username: string }>({ baseUrl, token, path: '/auth/me' });
      showToast(`认证服务正常，当前用户：${resp.data.username}`, 'success');
    } catch (err) {
      handleError(err);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">系统运维人员</p>
        <h2>系统运维工作台</h2>
        <p>监控服务健康状态、管理系统资源与运维告警。</p>
      </div>

      <article className="panel">
        <div className="panel-head">
          <h3>服务健康检查</h3>
          <p>检查 API 服务与认证服务的可用性。</p>
        </div>
        <div className="inline-actions" style={{ marginBottom: '1rem' }}>
          <button className="btn btn-primary" type="button" onClick={() => void checkHealth()} disabled={checking}>
            {checking ? '检查中…' : '检查 /health'}
          </button>
          <button className="btn btn-secondary" type="button" onClick={() => void checkAuthService()}>
            检查认证服务
          </button>
        </div>
        {healthResult && (
          <div className="summary-box">
            <strong>结果：</strong>{healthResult}
          </div>
        )}
      </article>

      <div className="panel-grid">
        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>实时资源监控</h3>
            <p>CPU、内存、GPU 使用率，向量索引内存占用实时大盘。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>资源监控大盘需要 Prometheus/Grafana 指标推送接口，将在后续版本中集成。</p>
          </div>
        </article>

        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>服务告警管理</h3>
            <p>配置延迟、错误率、内存告警阈值，接入通知渠道。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>告警规则配置与通知渠道管理将在后续版本中实现。</p>
          </div>
        </article>

        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>自动扩缩容</h3>
            <p>根据 QPS 负载自动调整索引服务实例数量。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>弹性扩缩容依赖 Kubernetes 编排系统集成，将在后续版本中实现。</p>
          </div>
        </article>

        <article className="panel reserved-card">
          <div className="panel-head">
            <h3>日志聚合与查询</h3>
            <p>聚合后端服务日志，支持关键词检索与时间范围过滤。</p>
          </div>
          <div className="reserved-notice">
            <span>功能预留</span>
            <p>日志聚合需要 ELK 或 Loki 日志系统集成，将在后续版本中实现。</p>
          </div>
        </article>
      </div>

      <div className={`toast ${toast.visible ? 'visible' : ''} ${toast.kind}`}>{toast.text}</div>
    </div>
  );
}
