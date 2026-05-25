import { useEffect, useMemo, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import type { Role } from '../types';

type NavItem = {
  path: string;
  label: string;
  roles?: Role[];
};

type NavGroup = {
  id: string;
  label: string;
  items: NavItem[];
};

// 树形分组导航：每组在角色过滤后若无任何子项，整组将不渲染
const NAV_GROUPS: NavGroup[] = [
  {
    id: 'overview',
    label: '概览',
    items: [
      { path: '/app/dashboard', label: '工作台' },
    ],
  },
  {
    id: 'business',
    label: '业务场景',
    items: [
      { path: '/app/clinical', label: '临床诊断', roles: ['user', 'admin'] },
      { path: '/app/experiment', label: '实验分析', roles: ['user', 'admin'] },
      { path: '/app/bioinfo', label: 'API 接入', roles: ['service', 'admin'] },
    ],
  },
  {
    id: 'rnd',
    label: '研发与运维',
    items: [
      { path: '/app/research', label: '研发工作台', roles: ['dev', 'admin'] },
      { path: '/app/database', label: '数据库管理', roles: ['admin'] },
      { path: '/app/ops', label: '系统运维', roles: ['admin'] },
    ],
  },
  {
    id: 'data',
    label: '数据资产',
    items: [
      { path: '/app/datasets', label: '数据集管理', roles: ['admin', 'dev', 'user', 'readonly', 'auditor'] },
      { path: '/app/indexes', label: '索引管理', roles: ['admin', 'dev'] },
    ],
  },
  {
    id: 'retrieval',
    label: '检索任务',
    items: [
      { path: '/app/search', label: '向量检索', roles: ['admin', 'dev', 'user', 'service', 'readonly'] },
      { path: '/app/batch-search', label: '批量检索', roles: ['admin', 'dev', 'user', 'service'] },
      { path: '/app/tasks', label: '任务监控', roles: ['admin', 'service', 'readonly', 'auditor'] },
    ],
  },
  {
    id: 'insight',
    label: '分析洞察',
    items: [
      { path: '/app/visualization', label: '可视化', roles: ['admin', 'dev', 'user', 'readonly', 'auditor'] },
      { path: '/app/metrics', label: '性能指标', roles: ['admin', 'dev', 'auditor'] },
      { path: '/app/reports', label: '诊断报告', roles: ['admin', 'user', 'auditor'] },
    ],
  },
  {
    id: 'system',
    label: '系统',
    items: [
      { path: '/app/users', label: '用户管理', roles: ['admin'] },
      { path: '/app/settings', label: '系统设置' },
    ],
  },
];

const COLLAPSE_KEY = 'ann.frontend.navCollapsed';

function loadCollapsed(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(COLLAPSE_KEY) || '{}') as Record<string, boolean>;
  } catch {
    return {};
  }
}

export function Sidebar() {
  const { user } = useAuth();
  const role = user?.role as Role | undefined;
  const location = useLocation();

  // 按角色过滤分组与项
  const visibleGroups = useMemo(() => {
    return NAV_GROUPS.map((g) => ({
      ...g,
      items: g.items.filter((it) => !it.roles || !role || it.roles.includes(role)),
    })).filter((g) => g.items.length > 0);
  }, [role]);

  // 当前路径所在的分组 id
  const activeGroupId = useMemo(() => {
    return visibleGroups.find((g) => g.items.some((it) => location.pathname.startsWith(it.path)))?.id;
  }, [visibleGroups, location.pathname]);

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(() => loadCollapsed());

  // 切换路由时，自动展开命中的分组
  useEffect(() => {
    if (activeGroupId && collapsed[activeGroupId]) {
      const next = { ...collapsed, [activeGroupId]: false };
      setCollapsed(next);
      localStorage.setItem(COLLAPSE_KEY, JSON.stringify(next));
    }
    // 仅在 activeGroupId 变化时触发
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeGroupId]);

  function toggleGroup(id: string) {
    const next = { ...collapsed, [id]: !collapsed[id] };
    setCollapsed(next);
    localStorage.setItem(COLLAPSE_KEY, JSON.stringify(next));
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">ANN</div>
        <div>
          <h1>Retrieval System</h1>
          <p>单细胞基因组检索平台</p>
        </div>
      </div>
      <nav className="nav-tree">
        {visibleGroups.map((group) => {
          const isCollapsed = !!collapsed[group.id];
          const isActiveGroup = group.id === activeGroupId;
          return (
            <div key={group.id} className={`nav-group${isActiveGroup ? ' active-group' : ''}`}>
              <button
                type="button"
                className={`nav-group-header${isCollapsed ? ' collapsed' : ''}`}
                onClick={() => toggleGroup(group.id)}
                aria-expanded={!isCollapsed}
              >
                <span className="nav-group-caret" aria-hidden="true">▾</span>
                <span className="nav-group-label">{group.label}</span>
                <span className="nav-group-count">{group.items.length}</span>
              </button>
              {!isCollapsed && (
                <div className="nav-group-items">
                  {group.items.map((item) => (
                    <NavLink key={item.path} to={item.path} className="nav-leaf">
                      <span className="nav-leaf-dot" aria-hidden="true" />
                      <span>{item.label}</span>
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
