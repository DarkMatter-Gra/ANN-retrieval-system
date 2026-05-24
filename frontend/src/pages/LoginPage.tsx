import { type FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiCall } from '../api';
import { useAuth } from '../auth/AuthContext';

export function LoginPage() {
  const { login, baseUrl } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    const form = new FormData(e.currentTarget);

    try {
      const resp = await apiCall<{ access_token: string }>({
        baseUrl,
        path: '/auth/login',
        method: 'POST',
        body: {
          username: String(form.get('username') || '').trim(),
          password: String(form.get('password') || '').trim(),
        },
      });
      await login(resp.data.access_token);
      navigate('/app/dashboard', { replace: true });
    } catch (err) {
      const msg =
        (err as { payload?: { message?: string }; message?: string })?.payload?.message ||
        (err as Error).message ||
        '登录失败，请检查用户名和密码';
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
          <h3 style={{ gridColumn: '1 / -1', margin: '0 0 0.3rem' }}>用户登录</h3>
          {error && <div className="form-error">{error}</div>}
          <label style={{ gridColumn: '1 / -1' }}>
            <span>用户名</span>
            <input name="username" type="text" required autoFocus autoComplete="username" />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            <span>密码</span>
            <input name="password" type="password" required autoComplete="current-password" />
          </label>
          <button className="btn btn-primary" type="submit" disabled={submitting} style={{ gridColumn: '1 / -1' }}>
            {submitting ? '登录中…' : '登录'}
          </button>
          <p className="auth-link">
            没有账号？<Link to="/register">立即注册</Link>
          </p>
        </form>
      </article>
    </div>
  );
}
