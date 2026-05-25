import { type FormEvent, useState } from 'react';
import { apiCall, DEFAULT_BASE_URL, normalizeBaseUrl } from '../api';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../lib/useToast';

export function SettingsPage() {
  const { baseUrl, setBaseUrl, token } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [urlInput, setUrlInput] = useState(baseUrl);
  const [healthStatus, setHealthStatus] = useState<string | null>(null);

  function handleSaveUrl(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const normalized = normalizeBaseUrl(urlInput);
    setBaseUrl(normalized);
    showToast(`API 地址已保存：${normalized}`, 'success');
    // 保存后立即做一次健康检查，方便用户感知是否连通
    void checkHealth();
  }

  async function checkHealth() {
    try {
      const origin = new URL(normalizeBaseUrl(urlInput) + '/').origin;
      const resp = await fetch(`${origin}/health`);
      const text = await resp.text();
      setHealthStatus(resp.ok ? `健康 (${resp.status})：${text.slice(0, 120)}` : `异常 (${resp.status})`);
      showToast(resp.ok ? '服务健康' : '服务异常', resp.ok ? 'success' : 'error');
    } catch (err) {
      const msg = (err as Error).message;
      setHealthStatus(`连接失败：${msg}`);
      showToast('连接失败', 'error');
    }
  }

  async function handleRefreshMe() {
    if (!token) { showToast('未登录', 'error'); return; }
    try {
      const resp = await apiCall<{ username: string; role: string }>({
        baseUrl, token, path: '/auth/me',
      });
      showToast(`当前用户：${resp.data.username}（${resp.data.role}）`, 'success');
    } catch (err) {
      handleError(err);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">系统设置</p>
        <h2>系统配置</h2>
        <p>配置 API 地址、检查服务健康状态。</p>
      </div>

      <article className="panel">
        <div className="panel-head"><h3>API 地址配置</h3></div>
        <form className="form-grid" onSubmit={handleSaveUrl}>
          <label style={{ gridColumn: '1 / -1' }}>
            <span>API Base URL</span>
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              spellCheck={false}
              placeholder={DEFAULT_BASE_URL}
            />
          </label>
          <button className="btn btn-primary" type="submit">保存地址</button>
          <button className="btn btn-secondary" type="button" onClick={() => void checkHealth()}>健康检查</button>
        </form>
        {healthStatus && (
          <div className="summary-box" style={{ marginTop: '1rem' }}>
            <strong>健康状态：</strong>{healthStatus}
          </div>
        )}
      </article>

      <article className="panel">
        <div className="panel-head">
          <h3>当前会话</h3>
          <p>查看当前登录用户信息。</p>
        </div>
        <div className="inline-actions">
          <button className="btn btn-secondary" type="button" onClick={() => void handleRefreshMe()}>刷新用户信息</button>
        </div>
      </article>

      <div className={`toast ${toast.visible ? 'visible' : ''} ${toast.kind}`}>{toast.text}</div>
    </div>
  );
}
