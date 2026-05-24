import { NavLink } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import type { Role } from '../types';

type NavItem = {
  path: string;
  label: string;
  roles?: Role[];
};

const NAV_ITEMS: NavItem[] = [
  { path: '/app/dashboard', label: '工作台' },
  { path: '/app/clinical', label: '临床诊断', roles: ['user', 'admin'] },
  { path: '/app/experiment', label: '实验分析', roles: ['user', 'admin'] },
  { path: '/app/bioinfo', label: 'API 接入', roles: ['service', 'admin'] },
  { path: '/app/research', label: '研发工作台', roles: ['dev', 'admin'] },
  { path: '/app/database', label: '数据库管理', roles: ['admin'] },
  { path: '/app/ops', label: '系统运维', roles: ['admin'] },
  { path: '/app/datasets', label: '数据集管理', roles: ['admin', 'dev', 'user', 'readonly', 'auditor'] },
  { path: '/app/indexes', label: '索引管理', roles: ['admin', 'dev'] },
  { path: '/app/search', label: '向量检索', roles: ['admin', 'dev', 'user', 'service', 'readonly'] },
  { path: '/app/batch-search', label: '批量检索', roles: ['admin', 'dev', 'user', 'service'] },
  { path: '/app/tasks', label: '任务监控', roles: ['admin', 'service', 'readonly', 'auditor'] },
  { path: '/app/visualization', label: '可视化', roles: ['admin', 'dev', 'user', 'readonly', 'auditor'] },
  { path: '/app/metrics', label: '性能指标', roles: ['admin', 'dev', 'auditor'] },
  { path: '/app/reports', label: '诊断报告', roles: ['admin', 'user', 'auditor'] },
  { path: '/app/users', label: '用户管理', roles: ['admin'] },
  { path: '/app/settings', label: '系统设置' },
];

export function Sidebar() {
  const { user } = useAuth();
  const role = user?.role as Role | undefined;

  const visible = NAV_ITEMS.filter((item) => !item.roles || !role || item.roles.includes(role));

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">ANN</div>
        <div>
          <h1>Retrieval System</h1>
          <p>单细胞基因组检索平台</p>
        </div>
      </div>
      <nav className="nav-list">
        {visible.map((item) => (
          <NavLink key={item.path} to={item.path}>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
