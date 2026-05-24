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
          role: String(form.get('role') || 'user').trim(),
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
            <select name="role" defaultValue="user">
              <option value="admin">admin — 系统管理员</option>
              <option value="dev">dev — 研发人员</option>
              <option value="user">user — 业务用户</option>
              <option value="service">service — 服务账号</option>
              <option value="readonly">readonly — 只读观察</option>
              <option value="auditor">auditor — 审计人员</option>
            </select>
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
