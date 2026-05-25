import { type FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiCall } from '../api';
import { useAuth } from '../auth/AuthContext';

export function RegisterPage() {
  const { baseUrl } = useAuth();
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError('');
    setSuccess('');
    setSubmitting(true);
    const form = new FormData(e.currentTarget);

    try {
      const resp = await apiCall<{ user_id: number; username: string; role: string }>({
        baseUrl,
        path: '/auth/register',
        method: 'POST',
        body: {
          username: String(form.get('username') || '').trim(),
          email: String(form.get('email') || '').trim(),
          password: String(form.get('password') || '').trim(),
          // 注册一律使用 user 角色，由管理员后续在用户管理页调整
          role: 'user',
        },
      });
      setSuccess(`注册成功！用户名：${resp.data.username}，角色：${resp.data.role}。请返回登录。`);
    } catch (err) {
      const msg =
        (err as { payload?: { message?: string }; message?: string })?.payload?.message ||
        (err as Error).message ||
        '注册失败';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <article className="auth-card">
        <div className="auth-brand">
          <div className="brand-mark">ANN</div>
          <div>
            <h2>ANN Retrieval System</h2>
            <p>单细胞基因组近似最近邻检索平台</p>
          </div>
        </div>
        <form className="form-grid" onSubmit={handleSubmit}>
          <h3 style={{ gridColumn: '1 / -1', margin: '0 0 0.3rem' }}>注册账号</h3>
          {error && <div className="form-error">{error}</div>}
          {success && <div className="form-success">{success}</div>}
          <label style={{ gridColumn: '1 / -1' }}>
            <span>用户名</span>
            <input name="username" type="text" required autoFocus autoComplete="username" />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            <span>邮箱</span>
            <input name="email" type="email" required autoComplete="email" />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            <span>密码</span>
            <input name="password" type="password" required autoComplete="new-password" />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            <span>角色</span>
            <input value="user — 业务用户（默认）" readOnly style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--text-soft)' }} />
            <small style={{ color: 'var(--text-soft)', fontSize: '0.8rem' }}>
              注册账号默认角色为 user。如需 admin / dev / service / readonly / auditor，请联系系统管理员在「用户管理」页调整。
            </small>
          </label>
          <button className="btn btn-primary" type="submit" disabled={submitting} style={{ gridColumn: '1 / -1' }}>
            {submitting ? '注册中…' : '注册'}
          </button>
          <p className="auth-link">
            已有账号？<Link to="/login">立即登录</Link>
          </p>
        </form>
      </article>
    </div>
  );
}
