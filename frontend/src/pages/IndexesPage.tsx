import { type FormEvent, useCallback, useEffect, useState } from 'react';
import { apiCall, clamp, formatBytes, safeJsonParse, statusLabel } from '../api';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../lib/useToast';
import type { IndexItem } from '../types';

const DS_KEY = 'ann.frontend.datasetId';
const IDX_KEY = 'ann.frontend.indexId';

export function IndexesPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  const [indexes, setIndexes] = useState<IndexItem[]>([]);
  const [selectedDatasetId] = useState<number | null>(() => Number(localStorage.getItem(DS_KEY) || 0) || null);
  const [selectedIndexId, setSelectedIndexId] = useState<number | null>(() => Number(localStorage.getItem(IDX_KEY) || 0) || null);
  const [indexDetail, setIndexDetail] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [auditComment, setAuditComment] = useState('上线审核说明');
  const [rollbackVersion, setRollbackVersion] = useState('');

  useEffect(() => {
    localStorage.setItem(IDX_KEY, String(selectedIndexId || ''));
  }, [selectedIndexId]);

  const loadList = useCallback(async () => {
    try {
      const resp = await apiCall<{ list: IndexItem[]; total: number }>({
        baseUrl, token, path: '/indexes',
        query: { dataset_id: selectedDatasetId ?? undefined, status: status || undefined, page, page_size: pageSize },
      });
      const list = resp.data.list ?? [];
      setIndexes(list);
      if (!selectedIndexId && list.length) setSelectedIndexId(list[0].index_id);
    } catch (err) {
      handleError(err);
      setIndexes([]);
    }
  }, [baseUrl, token, selectedDatasetId, status, page, pageSize, selectedIndexId, handleError]);

  const loadDetail = useCallback(async (id: number) => {
    try {
      const resp = await apiCall<Record<string, unknown>>({ baseUrl, token, path: `/indexes/${id}` });
      setIndexDetail(resp.data);
      setSelectedIndexId(id);
    } catch (err) {
      handleError(err);
    }
  }, [baseUrl, token, handleError]);

  useEffect(() => { void loadList(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      const resp = await apiCall<{ index_id?: number; task_id?: string }>({
        baseUrl, token, path: '/indexes', method: 'POST',
        body: {
          dataset_id: Number(form.get('dataset_id')),
          index_name: String(form.get('index_name') || '').trim(),
          index_type: String(form.get('index_type') || 'flat'),
          metric: String(form.get('metric') || 'l2'),
          params_json: safeJsonParse(form.get('params_json'), {}),
        },
      });
      if (resp.data.index_id) setSelectedIndexId(resp.data.index_id);
      showToast(`索引任务已创建：${resp.data.task_id ?? '-'}`, 'success');
      await loadList();
    } catch (err) {
      handleError(err);
    }
  }

  async function runAction(action: 'load' | 'publish' | 'rollback') {
    if (!selectedIndexId) { showToast('请先选择索引', 'error'); return; }
    try {
      if (action === 'load') {
        await apiCall({ baseUrl, token, path: `/indexes/${selectedIndexId}/load`, method: 'POST' });
      } else if (action === 'publish') {
        await apiCall({ baseUrl, token, path: `/indexes/${selectedIndexId}/publish`, method: 'POST', body: { audit_comment: auditComment } });
      } else {
        await apiCall({ baseUrl, token, path: `/indexes/${selectedIndexId}/rollback`, method: 'POST', body: { target_version: Number(rollbackVersion || 0) } });
      }
      await loadDetail(selectedIndexId);
      await loadList();
      showToast(`操作成功：${action}`, 'success');
    } catch (err) {
      handleError(err);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">索引管理</p>
        <h2>ANN 索引管理</h2>
        <p>创建、查看、加载、上线、回滚近似最近邻索引。</p>
      </div>

      <article className="panel">
        <div className="panel-head panel-head-row">
          <div><h3>索引列表</h3><p>当前数据集 ID：{selectedDatasetId ?? '-'}</p></div>
          <div className="inline-actions">
            <button className="btn btn-secondary" type="button" onClick={() => void loadList()}>刷新</button>
          </div>
        </div>
        <div className="toolbar">
          <label className="toolbar-field small">
            <span>状态</span>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">全部</option>
              <option value="pending">pending</option>
              <option value="running">running</option>
              <option value="done">done</option>
              <option value="failed">failed</option>
            </select>
          </label>
          <label className="toolbar-field small">
            <span>页码</span>
            <input type="number" min="1" value={page} onChange={(e) => setPage(Number(e.target.value) || 1)} />
          </label>
          <label className="toolbar-field small">
            <span>每页</span>
            <input type="number" min="1" max="100" value={pageSize} onChange={(e) => setPageSize(clamp(Number(e.target.value) || 20, 1, 100))} />
          </label>
          <button className="btn btn-primary" type="button" onClick={() => void loadList()}>查询</button>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>ID</th><th>名称</th><th>类型</th><th>度量</th><th>版本</th><th>状态</th><th>性能指标</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              {indexes.length ? indexes.map((idx) => (
                <tr key={idx.index_id} className={idx.index_id === selectedIndexId ? 'active-row' : ''}>
                  <td><strong>{idx.index_id}</strong></td>
                  <td>{idx.index_name ?? '-'}</td>
                  <td>{idx.index_type ?? '-'}</td>
                  <td>{idx.metric_type ?? idx.status ?? '-'}</td>
                  <td>{idx.version_no ?? '-'}</td>
                  <td>{statusLabel(idx.build_status ?? idx.status)}</td>
                  <td>召回：{idx.recall_score ?? idx.recall ?? '-'} / 内存：{formatBytes(idx.memory_cost_mb ?? idx.memory_usage ?? 0)}</td>
                  <td>
                    <div className="row-actions">
                      <button className="btn btn-secondary" type="button" onClick={() => setSelectedIndexId(idx.index_id)}>选中</button>
                      <button className="btn btn-secondary" type="button" onClick={() => void loadDetail(idx.index_id)}>详情</button>
                      <button className="btn btn-secondary" type="button" onClick={() => void runAction('load')}>加载</button>
                    </div>
                  </td>
                </tr>
              )) : (
                <tr><td colSpan={8}><div className="empty-state">暂无索引</div></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </article>

      <div className="detail-grid">
        <article className="panel">
          <div className="panel-head"><h3>创建索引任务</h3></div>
          <form className="form-grid" onSubmit={handleCreate}>
            <label>
              <span>数据集 ID</span>
              <input name="dataset_id" type="number" min="1" defaultValue={selectedDatasetId ?? ''} required />
            </label>
            <label>
              <span>索引名称</span>
              <input name="index_name" type="text" required />
            </label>
            <label>
              <span>索引类型</span>
              <select name="index_type" defaultValue="flat">
                <option value="flat">flat</option>
                <option value="ivf_pq">ivf_pq</option>
                <option value="hnsw">hnsw</option>
              </select>
            </label>
            <label>
              <span>度量</span>
              <select name="metric" defaultValue="l2">
                <option value="l2">l2</option>
                <option value="cosine">cosine</option>
                <option value="ip">ip</option>
              </select>
            </label>
            <label className="full">
              <span>参数 JSON</span>
              <textarea name="params_json" rows={4} defaultValue="{}" spellCheck={false} />
            </label>
            <button className="btn btn-primary full" type="submit">创建索引任务</button>
          </form>
        </article>

        <article className="panel">
          <div className="panel-head"><h3>索引操作</h3></div>
          <div className="form-grid">
            <label>
              <span>当前索引 ID</span>
              <input type="number" value={selectedIndexId ?? ''} readOnly />
            </label>
            <label>
              <span>回滚版本</span>
              <input type="number" min="1" value={rollbackVersion} onChange={(e) => setRollbackVersion(e.target.value)} placeholder="rollback 专用" />
            </label>
            <label className="full">
              <span>审核备注</span>
              <textarea rows={3} value={auditComment} onChange={(e) => setAuditComment(e.target.value)} spellCheck={false} />
            </label>
            <div className="inline-actions wrap full">
              <button className="btn btn-secondary" type="button" onClick={() => void runAction('load')}>加载到内存</button>
              <button className="btn btn-secondary" type="button" onClick={() => void runAction('publish')}>上线</button>
              <button className="btn btn-secondary" type="button" onClick={() => void runAction('rollback')}>回滚</button>
            </div>
          </div>
          <div className="detail-box" style={{ marginTop: '1rem' }}>
            {indexDetail
              ? <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: '0.88rem' }}>{JSON.stringify(indexDetail, null, 2)}</pre>
              : <span className="empty-state">可从列表中点击"详情"查看</span>}
          </div>
        </article>
      </div>

      <div className={`toast ${toast.visible ? 'visible' : ''} ${toast.kind}`}>{toast.text}</div>
    </div>
  );
}
