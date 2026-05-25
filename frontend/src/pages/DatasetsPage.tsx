import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { apiCall, formatDateTime, isTerminalStatus, statusLabel } from '../api';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../lib/useToast';
import type { DatasetDetail, DatasetItem, DatasetLogs } from '../types';

const DATASET_ID_KEY = 'ann.frontend.datasetId';

export function DatasetsPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  // List
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(false);

  // Selected
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const saved = localStorage.getItem(DATASET_ID_KEY);
    return saved ? Number(saved) : null;
  });
  const [detail, setDetail] = useState<DatasetDetail | null>(null);
  const [logs, setLogs] = useState<DatasetLogs | null>(null);

  // Upload
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await apiCall<{ list: DatasetItem[]; total: number }>({
        baseUrl, token,
        path: '/datasets',
        query: { page, page_size: pageSize, keyword: keyword || undefined },
      });
      setDatasets(resp.data.list ?? []);
      setTotal(resp.data.total ?? 0);
    } catch (err) {
      handleError(err);
      setDatasets([]);
    } finally {
      setLoading(false);
    }
  }, [baseUrl, token, page, pageSize, keyword, handleError]);

  const loadDetail = useCallback(async (id: number) => {
    try {
      const resp = await apiCall<DatasetDetail>({ baseUrl, token, path: `/datasets/${id}` });
      setDetail(resp.data);
    } catch (err) {
      handleError(err);
    }
  }, [baseUrl, token, handleError]);

  const loadLogs = useCallback(async (id: number) => {
    try {
      const resp = await apiCall<DatasetLogs>({ baseUrl, token, path: `/datasets/${id}/logs` });
      setLogs(resp.data);
    } catch (err) {
      handleError(err);
    }
  }, [baseUrl, token, handleError]);

  useEffect(() => { void loadList(); }, [loadList]);

  // Poll every 3 s while any dataset is still processing
  useEffect(() => {
    const hasPending = datasets.some(
      (d) => !isTerminalStatus(d.qc_status) || !isTerminalStatus(d.preprocess_status),
    );
    if (!hasPending) return;
    const id = window.setInterval(() => { void loadList(); }, 3000);
    return () => window.clearInterval(id);
  }, [datasets, loadList]);

  useEffect(() => {
    if (selectedId) {
      localStorage.setItem(DATASET_ID_KEY, String(selectedId));
      void loadDetail(selectedId);
      void loadLogs(selectedId);
    } else {
      localStorage.removeItem(DATASET_ID_KEY);
      setDetail(null);
      setLogs(null);
    }
  }, [selectedId, loadDetail, loadLogs]);

  async function handleDelete(id: number) {
    try {
      await apiCall({ baseUrl, token, path: `/datasets/${id}`, method: 'DELETE' });
      showToast(`数据集 ${id} 已删除`, 'success');
      if (selectedId === id) setSelectedId(null);
      void loadList();
    } catch (err) {
      handleError(err);
    }
  }

  async function handleUpload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) { showToast('请选择文件', 'error'); return; }

    setUploading(true);
    setUploadProgress(0);
    try {
      const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
      const initResp = await apiCall<{ upload_id: string; chunk_size: number }>({
        baseUrl, token,
        path: '/datasets/upload/init',
        method: 'POST',
        body: { filename: file.name, size: file.size, format: ext },
      });
      const { upload_id, chunk_size } = initResp.data;
      const totalChunks = Math.ceil(file.size / chunk_size);

      for (let i = 0; i < totalChunks; i++) {
        const blob = file.slice(i * chunk_size, (i + 1) * chunk_size);
        const fd = new FormData();
        fd.append('upload_id', upload_id);
        fd.append('chunk_index', String(i));
        fd.append('chunk_data', blob, file.name);
        await apiCall({ baseUrl, token, path: '/datasets/upload/chunk', method: 'POST', formData: fd });
        setUploadProgress(Math.round(((i + 1) / totalChunks) * 100));
      }

      const completeResp = await apiCall<{ dataset_id: number }>({
        baseUrl, token,
        path: '/datasets/upload/complete',
        method: 'POST',
        body: { upload_id },
      });
      showToast(`上传成功，数据集 ID: ${completeResp.data.dataset_id}`, 'success');
      if (fileRef.current) fileRef.current.value = '';
      void loadList();
    } catch (err) {
      handleError(err);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">数据集管理</p>
        <h2>数据集列表</h2>
        <p>上传、查看和管理单细胞基因组数据集。</p>
      </div>

      {/* List */}
      <article className="panel">
        <div className="panel-head panel-head-row">
          <div>
            <h3>数据集列表</h3>
            <p>共 {total} 个数据集（当前页 {datasets.length} 条）</p>
          </div>
          <div className="inline-actions">
            <button className="btn btn-secondary" type="button" onClick={() => void loadList()} disabled={loading}>
              {loading ? '加载中…' : '刷新'}
            </button>
          </div>
        </div>

        <div className="toolbar">
          <label className="toolbar-field">
            <span>关键词</span>
            <input
              type="text" value={keyword}
              onChange={(e) => { setKeyword(e.target.value); setPage(1); }}
              placeholder="数据集名称"
            />
          </label>
          <button className="btn btn-primary" type="button" onClick={() => void loadList()}>查询</button>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>名称</th>
                <th>格式</th>
                <th>细胞数</th>
                <th>基因数</th>
                <th>QC 状态</th>
                <th>预处理</th>
                <th>上传时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {datasets.length ? datasets.map((d) => (
                <tr
                  key={d.dataset_id}
                  className={d.dataset_id === selectedId ? 'active-row' : ''}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelectedId(d.dataset_id)}
                >
                  <td><strong>{d.dataset_id}</strong></td>
                  <td>{d.dataset_name ?? '-'}</td>
                  <td style={{ color: 'var(--accent)', fontSize: '0.88rem' }}>{d.file_format ?? '-'}</td>
                  <td>{d.cell_count?.toLocaleString() ?? '-'}</td>
                  <td>{d.gene_count?.toLocaleString() ?? '-'}</td>
                  <td style={{ fontSize: '0.88rem', color: isTerminalStatus(d.qc_status) ? (d.qc_status === 'failed' ? 'var(--danger)' : 'var(--accent)') : 'var(--text-soft)' }}>{statusLabel(d.qc_status)}</td>
                  <td style={{ fontSize: '0.88rem', color: isTerminalStatus(d.preprocess_status) ? (d.preprocess_status === 'failed' ? 'var(--danger)' : 'var(--accent)') : 'var(--text-soft)' }}>{statusLabel(d.preprocess_status)}</td>
                  <td style={{ fontSize: '0.85rem', color: 'var(--text-soft)' }}>{formatDateTime(d.created_at)}</td>
                  <td>
                    <div className="row-actions">
                      <button className="btn btn-secondary" type="button"
                        onClick={(ev) => { ev.stopPropagation(); setSelectedId(d.dataset_id); }}>
                        选中
                      </button>
                      <button
                        className="btn btn-secondary" type="button"
                        style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}
                        onClick={(ev) => { ev.stopPropagation(); void handleDelete(d.dataset_id); }}
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={9}>
                    <div className="empty-state">{loading ? '加载中…' : '暂无数据集'}</div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {total > 0 && (
          <div className="inline-actions spacing-top" style={{ justifyContent: 'center', gap: '0.5rem' }}>
            <button className="btn btn-secondary" type="button" onClick={() => setPage(1)} disabled={page === 1}>首页</button>
            <button className="btn btn-secondary" type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>上一页</button>
            <span style={{ padding: '0.84rem 0.6rem', color: 'var(--text-soft)', fontSize: '0.9rem' }}>{page} / {totalPages}</span>
            <button className="btn btn-secondary" type="button" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>下一页</button>
            <button className="btn btn-secondary" type="button" onClick={() => setPage(totalPages)} disabled={page >= totalPages}>末页</button>
          </div>
        )}
      </article>

      {/* Detail + Logs */}
      {selectedId && (
        <div className="detail-grid">
          <article className="panel">
            <div className="panel-head">
              <h3>数据集详情</h3>
              <p>数据集 ID：<strong style={{ color: 'var(--accent)' }}>{selectedId}</strong></p>
            </div>
            <div className="detail-box">
              {detail
                ? <pre style={{ margin: 0, fontSize: '0.84rem', color: 'var(--text-soft)', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{JSON.stringify(detail, null, 2)}</pre>
                : <span className="muted" style={{ fontSize: '0.9rem' }}>加载中…</span>
              }
            </div>
          </article>

          <article className="panel">
            <div className="panel-head">
              <h3>处理日志</h3>
            </div>
            {logs ? (
              <div style={{ display: 'grid', gap: '0.6rem' }}>
                {logs.steps?.map((s, i) => (
                  <div key={i} className="result-card">
                    <header>
                      <span style={{ fontWeight: 600, color: s.status === 'done' ? 'var(--accent)' : s.status === 'failed' ? 'var(--danger)' : 'var(--text)' }}>{s.step}</span>
                      <span style={{ color: 'var(--text-soft)', fontSize: '0.85rem' }}>{statusLabel(s.status)}{s.duration_ms ? ` · ${s.duration_ms}ms` : ''}</span>
                    </header>
                    {s.message && <p>{s.message}</p>}
                  </div>
                ))}
                {(logs.warnings?.length ?? 0) > 0 && (
                  <div style={{ padding: '0.7rem 0.9rem', borderRadius: 12, background: 'rgba(255,191,105,0.07)', border: '1px solid rgba(255,191,105,0.28)', color: 'var(--accent-3)', fontSize: '0.86rem' }}>
                    {logs.warnings?.join('\n')}
                  </div>
                )}
                {(logs.errors?.length ?? 0) > 0 && (
                  <div style={{ padding: '0.7rem 0.9rem', borderRadius: 12, background: 'rgba(255,114,114,0.07)', border: '1px solid rgba(255,114,114,0.28)', color: 'var(--danger)', fontSize: '0.86rem' }}>
                    {logs.errors?.join('\n')}
                  </div>
                )}
                {!logs.steps?.length && !logs.warnings?.length && !logs.errors?.length && (
                  <span className="muted" style={{ fontSize: '0.9rem', padding: '0.5rem' }}>暂无日志记录</span>
                )}
              </div>
            ) : (
              <span className="muted" style={{ fontSize: '0.9rem' }}>加载中…</span>
            )}
          </article>
        </div>
      )}

      {/* Upload */}
      <article className="panel">
        <div className="panel-head">
          <h3>上传数据集</h3>
          <p>支持 h5ad、mtx、csv 等格式，分块上传。</p>
        </div>
        <form className="form-grid upload-grid" onSubmit={(e) => void handleUpload(e)}>
          <label className="full">
            <span>选择文件</span>
            <input type="file" ref={fileRef} accept=".h5ad,.mtx,.csv,.h5,.loom" />
          </label>
          {uploading && (
            <div className="full" style={{ display: 'grid', gap: '0.4rem' }}>
              <div style={{ height: 8, borderRadius: 4, background: 'rgba(156,175,199,0.14)', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${uploadProgress}%`, background: 'var(--accent)', transition: 'width 0.2s ease', borderRadius: 4 }} />
              </div>
              <span style={{ color: 'var(--text-soft)', fontSize: '0.86rem' }}>上传中… {uploadProgress}%</span>
            </div>
          )}
          <button className="btn btn-primary full" type="submit" disabled={uploading}>
            {uploading ? `上传中 ${uploadProgress}%` : '开始上传'}
          </button>
        </form>
      </article>

      <div className={`toast ${toast.visible ? 'visible' : ''} ${toast.kind}`}>{toast.text}</div>
    </div>
  );
}
