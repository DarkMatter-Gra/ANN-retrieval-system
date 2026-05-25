import { type FormEvent, useCallback, useEffect, useState } from 'react';
import { apiCall, formatDateTime } from '../api';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../lib/useToast';

type UserItem = {
  user_id: number;
  username: string;
  email: string;
  role: string;
  status: string;
  quota_limit: number;
  created_at?: string;
};

const ROLE_OPTIONS = ['', 'admin', 'dev', 'user', 'service', 'readonly', 'auditor'];
const STATUS_OPTIONS = ['', 'active', 'disabled', 'locked'];

const STATUS_LABEL: Record<string, string> = {
  active: '正常',
  disabled: '已禁用',
  locked: '已锁定',
  deleted: '已删除',
};

const ROLE_LABEL: Record<string, string> = {
  admin: '系统管理员',
  dev: '研发人员',
  user: '业务用户',
  service: '服务账号',
  readonly: '只读观察',
  auditor: '审计人员',
};

export function UsersPage() {
  const { token, baseUrl } = useAuth();
  const { toast, showToast, handleError } = useToast();

  // List state
  const [users, setUsers] = useState<UserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [filterRole, setFilterRole] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(false);

  // CRUD state
  const [targetUserId, setTargetUserId] = useState('');
  const [newRole, setNewRole] = useState('user');
  const [newStatus, setNewStatus] = useState('active');
  const [newPassword, setNewPassword] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await apiCall<{ list: UserItem[]; total: number }>({
        baseUrl,
        token,
        path: '/users',
        query: {
          page,
          page_size: pageSize,
          keyword: keyword || undefined,
          role: filterRole || undefined,
          status: filterStatus || undefined,
        },
      });
      setUsers(resp.data.list ?? []);
      setTotal(resp.data.total ?? 0);
    } catch (err) {
      handleError(err);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, [baseUrl, token, page, pageSize, keyword, filterRole, filterStatus, handleError]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  function selectUser(uid: number) {
    setTargetUserId(String(uid));
  }

  async function handleUpdateRole(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!targetUserId) { showToast('请输入或选择用户 ID', 'error'); return; }
    try {
      await apiCall({
        baseUrl, token, path: `/users/${targetUserId}`, method: 'PATCH',
        body: { role: newRole },
      });
      showToast(`用户 ${targetUserId} 角色已更新为 ${newRole}`, 'success');
      void loadUsers();
    } catch (err) {
      handleError(err);
    }
  }

  async function handleUpdateStatus(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!targetUserId) { showToast('请输入或选择用户 ID', 'error'); return; }
    try {
      await apiCall({
        baseUrl, token, path: `/users/${targetUserId}`, method: 'PATCH',
        body: { status: newStatus },
      });
      showToast(`用户 ${targetUserId} 状态已更新为 ${newStatus}`, 'success');
      void loadUsers();
    } catch (err) {
      handleError(err);
    }
  }

  async function handleResetPassword(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!targetUserId) { showToast('请输入或选择用户 ID', 'error'); return; }
    if (!newPassword) { showToast('请输入新密码', 'error'); return; }
    if (newPassword.length < 8) { showToast('新密码至少 8 位', 'error'); return; }
    try {
      await apiCall({
        baseUrl, token, path: `/users/${targetUserId}/reset-password`, method: 'POST',
        body: { new_password: newPassword },
      });
      showToast(`用户 ${targetUserId} 密码已重置`, 'success');
      setNewPassword('');
    } catch (err) {
      handleError(err);
    }
  }

  async function handleDelete() {
    if (!targetUserId) { showToast('请输入或选择用户 ID', 'error'); return; }
    if (!confirmDelete) { showToast('请勾选确认删除', 'error'); return; }
    try {
      await apiCall({ baseUrl, token, path: `/users/${targetUserId}`, method: 'DELETE' });
      showToast(`用户 ${targetUserId} 已删除`, 'success');
      setTargetUserId('');
      setConfirmDelete(false);
      void loadUsers();
    } catch (err) {
      handleError(err);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">用户管理</p>
        <h2>系统用户管理</h2>
        <p>查看所有用户，修改角色/状态，重置密码，删除账号。</p>
      </div>

      {/* ── 用户列表 ── */}
      <article className="panel">
        <div className="panel-head panel-head-row">
          <div>
            <h3>用户列表</h3>
            <p>共 {total} 个用户（当前页 {users.length} 条）</p>
          </div>
          <div className="inline-actions">
            <button className="btn btn-secondary" type="button" onClick={() => void loadUsers()} disabled={loading}>
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
              placeholder="用户名或邮箱"
            />
          </label>
          <label className="toolbar-field small">
            <span>角色</span>
            <select value={filterRole} onChange={(e) => { setFilterRole(e.target.value); setPage(1); }}>
              {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{r || '全部'}</option>)}
            </select>
          </label>
          <label className="toolbar-field small">
            <span>状态</span>
            <select value={filterStatus} onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}>
              {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{STATUS_LABEL[s] ?? '全部'}</option>)}
            </select>
          </label>
          <button className="btn btn-primary" type="button" onClick={() => void loadUsers()}>查询</button>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>用户名</th>
                <th>邮箱</th>
                <th>角色</th>
                <th>状态</th>
                <th>配额</th>
                <th>注册时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.length ? users.map((u) => (
                <tr
                  key={u.user_id}
                  className={String(u.user_id) === targetUserId ? 'active-row' : ''}
                  style={{ cursor: 'pointer' }}
                  onClick={() => selectUser(u.user_id)}
                >
                  <td><strong>{u.user_id}</strong></td>
                  <td>{u.username}</td>
                  <td style={{ color: 'var(--text-soft)', fontSize: '0.88rem' }}>{u.email}</td>
                  <td>
                    <span style={{
                      padding: '0.2rem 0.55rem', borderRadius: '6px', fontSize: '0.8rem',
                      background: 'rgba(105,226,195,0.12)', color: 'var(--accent)',
                    }}>
                      {ROLE_LABEL[u.role] ?? u.role}
                    </span>
                  </td>
                  <td>
                    <span style={{
                      color: u.status === 'active' ? 'var(--accent)' : 'var(--danger)',
                      fontSize: '0.88rem',
                    }}>
                      {STATUS_LABEL[u.status] ?? u.status}
                    </span>
                  </td>
                  <td>{u.quota_limit}</td>
                  <td style={{ fontSize: '0.85rem', color: 'var(--text-soft)' }}>{formatDateTime(u.created_at)}</td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={(ev) => { ev.stopPropagation(); selectUser(u.user_id); }}
                      >
                        选中
                      </button>
                    </div>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={8}>
                    <div className="empty-state">{loading ? '加载中…' : '暂无用户数据'}</div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="inline-actions spacing-top" style={{ justifyContent: 'center', gap: '0.5rem' }}>
          <button className="btn btn-secondary" type="button" onClick={() => setPage(1)} disabled={page === 1}>首页</button>
          <button className="btn btn-secondary" type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>上一页</button>
          <span style={{ padding: '0.84rem 0.6rem', color: 'var(--text-soft)', fontSize: '0.9rem' }}>
            {page} / {totalPages}
          </span>
          <button className="btn btn-secondary" type="button" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>下一页</button>
          <button className="btn btn-secondary" type="button" onClick={() => setPage(totalPages)} disabled={page >= totalPages}>末页</button>
        </div>
      </article>

      {/* ── 操作面板 ── */}
      <div className="detail-grid">
        <article className="panel">
          <div className="panel-head">
            <h3>修改角色 / 状态</h3>
            <p>选中用户 ID：<strong style={{ color: 'var(--accent)' }}>{targetUserId || '未选择（点击列表行选中）'}</strong></p>
          </div>

          <form className="form-grid" onSubmit={handleUpdateRole} style={{ marginBottom: '1rem' }}>
            <label>
              <span>用户 ID</span>
              <input type="number" min="1" value={targetUserId} onChange={(e) => setTargetUserId(e.target.value)} placeholder="user_id" />
            </label>
            <label>
              <span>新角色</span>
              <select value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                {ROLE_OPTIONS.filter(Boolean).map((r) => (
                  <option key={r} value={r}>{r} — {ROLE_LABEL[r]}</option>
                ))}
              </select>
            </label>
            <button className="btn btn-primary full" type="submit">更新角色</button>
          </form>

          <form className="form-grid" onSubmit={handleUpdateStatus}>
            <label>
              <span>新状态</span>
              <select value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                <option value="active">active — 正常</option>
                <option value="disabled">disabled — 禁用</option>
                <option value="locked">locked — 锁定</option>
              </select>
            </label>
            <button className="btn btn-secondary full" type="submit">更新状态</button>
          </form>
        </article>

        <article className="panel">
          <div className="panel-head"><h3>重置密码</h3></div>
          <form className="form-grid" onSubmit={handleResetPassword} style={{ marginBottom: '1.2rem' }}>
            <label>
              <span>用户 ID</span>
              <input type="number" min="1" value={targetUserId} onChange={(e) => setTargetUserId(e.target.value)} placeholder="user_id" />
            </label>
            <label>
              <span>新密码（≥8 位）</span>
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" />
            </label>
            <button className="btn btn-secondary full" type="submit">重置密码</button>
          </form>

          <div className="panel-head" style={{ borderTop: '1px solid var(--line)', paddingTop: '1rem' }}>
            <h3 style={{ color: 'var(--danger)' }}>删除用户</h3>
            <p>软删除，状态标记为 deleted，不可登录。</p>
          </div>
          <div className="form-grid">
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', gridColumn: '1 / -1' }}>
              <input
                type="checkbox" checked={confirmDelete}
                onChange={(e) => setConfirmDelete(e.target.checked)}
                style={{ width: 'auto' }}
              />
              <span>确认删除用户 {targetUserId || '?'}</span>
            </label>
            <button
              className="btn btn-secondary full" type="button"
              style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}
              onClick={() => void handleDelete()}
            >
              删除用户
            </button>
          </div>
        </article>
      </div>

      <div className={`toast ${toast.visible ? 'visible' : ''} ${toast.kind}`}>{toast.text}</div>
    </div>
  );
}
