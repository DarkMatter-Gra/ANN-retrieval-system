import { type FormEvent, useRef, useState } from 'react';
import { apiCall, clamp, safeJsonParse, statusLabel } from '../api';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../lib/useToast';
import type { TaskSnapshot } from '../types';

const DS_KEY = 'ann.frontend.datasetId';
const IDX_KEY = 'ann.frontend.indexId';

export function BatchSearchPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [task, setTask] = useState<TaskSnapshot | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const timerRef = useRef<number | null>(null);

  async function loadTask(taskId: string): Promise<TaskSnapshot | null> {
    try {
      const resp = await apiCall<TaskSnapshot>({ baseUrl, token, path: `/tasks/${taskId}` });
      setTask(resp.data);
      return resp.data;
    } catch (err) {
      handleError(err);
      return null;
    }
  }

  async function pollTask(taskId: string) {
    if (timerRef.current) { window.clearInterval(timerRef.current); timerRef.current = null; }

    const refresh = async () => {
      const cur = await loadTask(taskId);
      if (cur && (cur.status === 'done' || cur.status === 'failed')) {
        if (timerRef.current) { window.clearInterval(timerRef.current); timerRef.current = null; }
        showToast(cur.status === 'done' ? '批量任务已完成' : '批量任务失败', cur.status === 'done' ? 'success' : 'error');
      }
    };

    await refresh();
    timerRef.current = window.setInterval(() => { void refresh(); }, 3000);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    const form = new FormData(e.currentTarget);

    try {
      const resp = await apiCall<{ task_id: string; status: string }>({
        baseUrl, token, path: '/batch-search', method: 'POST',
        body: {
          dataset_id: Number(form.get('dataset_id')),
          index_id: Number(form.get('index_id')),
          queries: safeJsonParse(form.get('queries'), []),
          top_k: clamp(Number(form.get('top_k') || 10), 1, 1000),
          mode: String(form.get('mode') || 'ann'),
          export_format: String(form.get('export_format') || 'json'),
        },
      });
      setTask({ task_id: resp.data.task_id, status: resp.data.status, progress: 0, type: 'batch_search' });
      showToast(`批量任务已提交：${resp.data.task_id}`, 'success');
      void pollTask(resp.data.task_id);
    } catch (err) {
      handleError(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">批量检索</p>
        <h2>批量 ANN 检索任务</h2>
        <p>提交异步批量检索任务，实时轮询任务状态。</p>
      </div>

      <div className="detail-grid">
        <article className="panel">
          <div className="panel-head"><h3>提交批量任务</h3></div>
          <form className="form-grid" onSubmit={handleSubmit}>
            <label>
              <span>数据集 ID</span>
              <input name="dataset_id" type="number" min="1" defaultValue={localStorage.getItem(DS_KEY) || ''} required />
            </label>
            <label>
              <span>索引 ID</span>
              <input name="index_id" type="number" min="1" defaultValue={localStorage.getItem(IDX_KEY) || ''} required />
            </label>
            <label>
              <span>Top K</span>
              <input name="top_k" type="number" min="1" max="1000" defaultValue={10} />
            </label>
            <label>
              <span>模式</span>
              <select name="mode" defaultValue="ann">
                <option value="ann">ann</option>
                <option value="exact">exact</option>
              </select>
            </label>
            <label>
              <span>导出格式</span>
              <select name="export_format" defaultValue="json">
                <option value="json">json</option>
                <option value="csv">csv</option>
              </select>
            </label>
            <label className="full">
              <span>queries JSON</span>
              <textarea
                name="queries"
                rows={8}
                defaultValue={'[{"query_type":"cell_id","cell_id":"cell_0001"}]'}
                spellCheck={false}
              />
            </label>
            <button className="btn btn-primary full" type="submit" disabled={submitting}>
              {submitting ? '提交中…' : '提交批量任务'}
            </button>
          </form>
        </article>

        <article className="panel">
          <div className="panel-head"><h3>任务状态</h3></div>
          <div className="summary-box">
            {task ? (
              <>
                <div><strong>task_id：</strong>{task.task_id ?? '-'}</div>
                <div><strong>类型：</strong>{task.type ?? '-'}</div>
                <div><strong>状态：</strong>{statusLabel(task.status)}</div>
                <div><strong>进度：</strong>{task.progress ?? 0}%</div>
                {task.error_message && <div><strong>错误：</strong><span style={{ color: 'var(--danger)' }}>{task.error_message}</span></div>}
                {task.result_url && (
                  <div>
                    <strong>结果：</strong>
                    <a href={task.result_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>下载结果</a>
                  </div>
                )}
              </>
            ) : <div className="empty-state">提交任务后状态将显示在这里（每 3 秒自动刷新）</div>}
          </div>
          {task && (
            <div style={{ marginTop: '1rem' }}>
              <div style={{ height: '8px', borderRadius: '4px', background: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${task.progress ?? 0}%`, background: 'linear-gradient(90deg, #69e2c3, #7fa8ff)', transition: 'width 0.5s ease', borderRadius: '4px' }} />
              </div>
            </div>
          )}
        </article>
      </div>

      <div className={`toast ${toast.visible ? 'visible' : ''} ${toast.kind}`}>{toast.text}</div>
    </div>
  );
}
