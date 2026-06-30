import { useEffect, useMemo, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../types";

type IconKey =
  | "dashboard"
  | "clinical"
  | "experiment"
  | "research"
  | "database"
  | "ops"
  | "datasets"
  | "indexes"
  | "search"
  | "ai"
  | "tasks"
  | "viz"
  | "metrics"
  | "reports"
  | "users"
  | "settings";

type NavItem = {
  path: string;
  label: string;
  icon: IconKey;
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
    id: "overview",
    label: "概览",
    items: [{ path: "/app/dashboard", label: "工作台", icon: "dashboard" }],
  },
  {
    id: "business",
    label: "业务场景",
    items: [
      {
        path: "/app/clinical",
        label: "临床诊断",
        icon: "clinical",
        roles: ["user", "admin"],
      },
      {
        path: "/app/experiment",
        label: "实验分析",
        icon: "experiment",
        roles: ["user", "admin"],
      },
    ],
  },
  {
    id: "rnd",
    label: "研发与运维",
    items: [
      {
        path: "/app/research",
        label: "研发工作台",
        icon: "research",
        roles: ["dev", "admin"],
      },
      {
        path: "/app/database",
        label: "数据库管理",
        icon: "database",
        roles: ["admin"],
      },
      { path: "/app/ops", label: "系统运维", icon: "ops", roles: ["admin"] },
    ],
  },
  {
    id: "data",
    label: "数据资产",
    items: [
      {
        path: "/app/datasets",
        label: "数据集管理",
        icon: "datasets",
        roles: ["admin", "dev", "user", "readonly", "auditor"],
      },
      {
        path: "/app/indexes",
        label: "索引管理",
        icon: "indexes",
        roles: ["admin", "dev"],
      },
    ],
  },
  {
    id: "retrieval",
    label: "检索任务",
    items: [
      {
        path: "/app/search",
        label: "向量检索",
        icon: "search",
        roles: ["admin", "dev", "user", "service", "readonly"],
      },
      {
        path: "/app/ai-search",
        label: "AI 智能检索",
        icon: "ai",
        roles: ["admin", "dev", "user", "service", "readonly"],
      },
      {
        path: "/app/tasks",
        label: "任务监控",
        icon: "tasks",
        roles: ["admin", "service", "readonly", "auditor"],
      },
    ],
  },
  {
    id: "insight",
    label: "分析洞察",
    items: [
      {
        path: "/app/visualization",
        label: "可视化",
        icon: "viz",
        roles: ["admin", "dev", "user", "readonly", "auditor"],
      },
      {
        path: "/app/metrics",
        label: "性能指标",
        icon: "metrics",
        roles: ["admin", "dev", "auditor"],
      },
      {
        path: "/app/reports",
        label: "诊断报告",
        icon: "reports",
        roles: ["admin", "user", "auditor"],
      },
    ],
  },
  {
    id: "system",
    label: "系统",
    items: [
      {
        path: "/app/users",
        label: "用户管理",
        icon: "users",
        roles: ["admin"],
      },
      { path: "/app/settings", label: "系统设置", icon: "settings" },
    ],
  },
];

const ICON_PATHS: Record<IconKey, string> = {
  dashboard: "M4 13h6V4H4v9Zm10 7h6v-9h-6v9ZM4 20h6v-5H4v5ZM14 9h6V4h-6v5Z",
  clinical: "M12 21s-7-4.35-9-8.5C1.5 9 3 5.5 6.5 5.5c2 0 3.5 1.5 5.5 3.5 2-2 3.5-3.5 5.5-3.5C21 5.5 22.5 9 21 12.5 19 16.65 12 21 12 21Z",
  experiment: "M9 3h6M10 3v6.5L5 19a1.5 1.5 0 0 0 1.4 2.2h11.2A1.5 1.5 0 0 0 19 19l-5-9.5V3",
  research: "M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3Zm0 0v18M4 7.5l8 4.5 8-4.5",
  database: "M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3Zm8 3v6c0 1.7-3.6 3-8 3s-8-1.3-8-3V6m16 6v6c0 1.7-3.6 3-8 3s-8-1.3-8-3v-6",
  ops: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7.4-3a7.4 7.4 0 0 0-.1-1.3l2-1.6-2-3.4-2.4 1a7.3 7.3 0 0 0-2.2-1.3l-.4-2.5H9.7l-.4 2.5a7.3 7.3 0 0 0-2.2 1.3l-2.4-1-2 3.4 2 1.6a7.4 7.4 0 0 0 0 2.6l-2 1.6 2 3.4 2.4-1a7.3 7.3 0 0 0 2.2 1.3l.4 2.5h4.6l.4-2.5a7.3 7.3 0 0 0 2.2-1.3l2.4 1 2-3.4-2-1.6c.07-.43.1-.86.1-1.3Z",
  datasets: "M4 6h16M4 12h16M4 18h16M8 3v18",
  indexes: "M4 7l8-4 8 4-8 4-8-4Zm0 5l8 4 8-4M4 17l8 4 8-4",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm10 3-5.5-5.5",
  ai: "M12 3v3m0 12v3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1M3 12h3m12 0h3M5.6 18.4l2.1-2.1m8.6-8.6 2.1-2.1M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z",
  tasks: "M9 11l3 3 8-8M4 6h7M4 12h4M4 18h7",
  viz: "M3 3v18h18M8 16l3.5-4 3 2.5L20 8",
  metrics: "M4 20V10m5 10V4m5 16v-7m5 7V8",
  reports: "M8 3h6l4 4v12a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm5 0v5h5M9 13h6M9 17h4",
  users: "M16 18v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 16.5V18M9.5 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm10.5 8v-1.5a3.5 3.5 0 0 0-2.6-3.4M15 4.2a3 3 0 0 1 0 5.8",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7.4-3c0-.44-.04-.87-.1-1.3l2-1.6-2-3.4-2.4 1a7.3 7.3 0 0 0-2.2-1.3l-.4-2.5H9.7l-.4 2.5a7.3 7.3 0 0 0-2.2 1.3l-2.4-1-2 3.4 2 1.6a7.4 7.4 0 0 0 0 2.6l-2 1.6 2 3.4 2.4-1a7.3 7.3 0 0 0 2.2 1.3l.4 2.5h4.6l.4-2.5a7.3 7.3 0 0 0 2.2-1.3l2.4 1 2-3.4-2-1.6c.06-.43.1-.86.1-1.3Z",
};

function NavIcon({ name }: { name: IconKey }) {
  return (
    <svg
      className="nav-leaf-icon"
      viewBox="0 0 24 24"
      width="17"
      height="17"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={ICON_PATHS[name]} />
    </svg>
  );
}

const COLLAPSE_KEY = "ann.frontend.navCollapsed";

function loadCollapsed(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(COLLAPSE_KEY) || "{}") as Record<
      string,
      boolean
    >;
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
      items: g.items.filter(
        (it) => !it.roles || !role || it.roles.includes(role),
      ),
    })).filter((g) => g.items.length > 0);
  }, [role]);

  // 当前路径所在的分组 id
  const activeGroupId = useMemo(() => {
    return visibleGroups.find((g) =>
      g.items.some((it) => location.pathname.startsWith(it.path)),
    )?.id;
  }, [visibleGroups, location.pathname]);

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(() =>
    loadCollapsed(),
  );

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
            <div
              key={group.id}
              className={`nav-group${isActiveGroup ? " active-group" : ""}`}
            >
              <button
                type="button"
                className={`nav-group-header${isCollapsed ? " collapsed" : ""}`}
                onClick={() => toggleGroup(group.id)}
                aria-expanded={!isCollapsed}
              >
                <span className="nav-group-label">{group.label}</span>
                <span className="nav-group-count">{group.items.length}</span>
                <span className="nav-group-caret" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m6 9 6 6 6-6" />
                  </svg>
                </span>
              </button>
              {!isCollapsed && (
                <div className="nav-group-items">
                  {group.items.map((item) => (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      className="nav-leaf"
                    >
                      <span className="nav-leaf-glyph" aria-hidden="true">
                        <NavIcon name={item.icon} />
                      </span>
                      <span className="nav-leaf-label">{item.label}</span>
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
