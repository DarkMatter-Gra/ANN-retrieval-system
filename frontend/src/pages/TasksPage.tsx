import { useEffect, useRef, useState } from 'react';
import { absoluteUrl, apiCall, formatDateTime, statusLabel } from '../api';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../lib/useToast';
import type { TaskSnapshot } from '../types';

const TASK_KEY = 'ann.frontend.taskId';

export function TasksPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [taskId, setTaskId] = useState(() => localStorage.getItem(TASK_KEY) || '');
  const [task, setTask] = useState<TaskSnapshot | null>(null);
  const [exportFormat, setExportFormat] = useState<'json' | 'csv'>('json');
  const timerRef = useRef<number | null>(null);

  // 卸载时清理定时器
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  async function loadTask(id: string): Promise<TaskSnapshot | null> {
    if (!id) { showToast('请输入 task_id', 'error'); return null; }
    localStorage.setItem(TASK_KEY, id);
    try {
      const resp = await apiCall<TaskSnapshot>({ baseUrl, token, path: `/tasks/${id}` });
      setTask(resp.data);
      return resp.data;
    } catch (err) {
      handleError(err);
      return null;
    }
  }

  function startPolling() {
    if (!taskId) { showToast('请输入 task_id', 'error'); return; }
    if (timerRef.current) { window.clearInterval(timerRef.current); timerRef.current = null; }

    const refresh = async () => {
      const cur = await loadTask(taskId);
      if (cur && (cur.status === 'done' || cur.status === 'failed')) {
        if (timerRef.current) { window.clearInterval(timerRef.current); timerRef.current = null; }
        showToast(cur.status === 'done' ? '任务已完成' : '任务失败', cur.status === 'done' ? 'success' : 'error');
      }
    };

    void refresh();
    timerRef.current = window.setInterval(() => { void refresh(); }, 3000);
    showToast('已开始轮询，每 3 秒自动刷新', 'info');
  }

  async function handleExport() {
    if (!taskId) { showToast('请输入 task_id', 'error'); return; }
    try {
      const resp = await apiCall<{ download_url: string }>({
        baseUrl, token, path: `/tasks/${taskId}/export`, query: { format: exportFormat },
      });
      const url = absoluteUrl(baseUrl, resp.data.download_url);
      window.open(url, '_blank', 'noreferrer');
      showToast('已获取导出链接', 'success');
    } catch (err) {
      handleError(err);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">任务监控</p>
        <h2>任务查询与导出</h2>
        <p>查看检索任务、批量任务状态，并导出任务结果。</p>
      </div>

      <article className="panel">
        <div className="panel-head"><h3>任务查询</h3></div>
        <div className="toolbar">
          <label className="toolbar-field wide">
            <span>任务 ID</span>
            <input
              type="text"
              value={taskId}
              onChange={(e) => setTaskId(e.target.value.trim())}
              placeholder="task_id"
            />
          </label>
          <button className="btn btn-primary" type="button" onClick={() => void loadTask(taskId)}>查询</button>
          <button className="btn btn-secondary" type="button" onClick={startPolling}>开始轮询</button>
        </div>

        <div className="summary-box">
          {task ? (
            <>
              <div><strong>task_id：</strong>{task.task_id ?? '-'}</div>
              <div><strong>类型：</strong>{task.type ?? '-'}</div>
              <div><strong>状态：</strong>{statusLabel(task.status)}</div>
              <div><strong>进度：</strong>{task.progress ?? 0}%</div>
              <div><strong>开始时间：</strong>{formatDateTime(task.started_at)}</div>
              <div><strong>结束时间：</strong>{formatDateTime(task.finished_at)}</div>
              {task.result_url && (
                <div><strong>结果 URL：</strong><a href={absoluteUrl(baseUrl, task.result_url)} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>{task.result_url}</a></div>
              )}
              {task.error_message && (
                <div><strong>错误信息：</strong><span style={{ color: 'var(--danger)' }}>{task.error_message}</span></div>
              )}
            </>
          ) : <span className="empty-state">任务状态将显示在这里</span>}
        </div>

        <div className="inline-actions spacing-top">
          <label className="toolbar-field small">
            <span>导出格式</span>
            <select value={exportFormat} onChange={(e) => setExportFormat(e.target.value as 'json' | 'csv')}>
              <option value="json">json</option>
              <option value="csv">csv</option>
            </select>
          </label>
          <button className="btn btn-secondary" type="button" onClick={() => void handleExport()}>获取导出链接</button>
        </div>
      </article>

      <div className={`toast ${toast.visible ? 'visible' : ''} ${toast.kind}`}>{toast.text}</div>
    </div>
  );
}
