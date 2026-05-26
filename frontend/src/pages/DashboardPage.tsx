import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiCall } from "../api";
import { useAuth } from "../auth/AuthContext";
import type { DatasetItem, IndexItem } from "../types";

type QuickLink = {
  path: string;
  label: string;
  desc: string;
  roles?: string[];
};
type LinkGroup = {
  id: string;
  title: string;
  subtitle: string;
  tone: "teal" | "blue" | "amber" | "violet";
  links: QuickLink[];
};

const LINK_GROUPS: LinkGroup[] = [
  {
    id: "workbench",
    title: "业务工作台",
    subtitle: "面向不同角色的端到端工作流入口",
    tone: "teal",
    links: [
      {
        path: "/app/clinical",
        label: "临床诊断",
        desc: "相似细胞检索 · 表型参考报告",
        roles: ["user", "admin"],
      },
      {
        path: "/app/experiment",
        label: "实验分析",
        desc: "预处理监控 · 质控与表型检索",
        roles: ["user", "admin"],
      },
      {
        path: "/app/bioinfo",
        label: "API 接入",
        desc: "程序化检索 · 批量任务管理",
        roles: ["service", "admin"],
      },
      {
        path: "/app/research",
        label: "研发工作台",
        desc: "索引构建 · 算法调优 · 评估",
        roles: ["dev", "admin"],
      },
      {
        path: "/app/database",
        label: "数据库管理",
        desc: "公共数据集 · 版本与权限",
        roles: ["admin"],
      },
      {
        path: "/app/ops",
        label: "系统运维",
        desc: "服务监控 · 资源调度 · 告警",
        roles: ["admin"],
      },
    ],
  },
  {
    id: "data",
    title: "数据与索引",
    subtitle: "管理数据集与近似最近邻索引生命周期",
    tone: "blue",
    links: [
      {
        path: "/app/datasets",
        label: "数据集管理",
        desc: "上传 · 元数据 · 处理日志",
        roles: ["admin", "dev", "user", "readonly", "auditor"],
      },
      {
        path: "/app/indexes",
        label: "索引管理",
        desc: "创建 · 加载 · 上线 · 回滚",
        roles: ["admin", "dev"],
      },
    ],
  },
  {
    id: "search",
    title: "检索与任务",
    subtitle: "执行检索并跟踪异步任务执行状态",
    tone: "amber",
    links: [
      {
        path: "/app/search",
        label: "向量检索",
        desc: "单次 ANN · cell_id / 向量",
        roles: ["admin", "dev", "user", "service", "readonly"],
      },
      {
        path: "/app/batch-search",
        label: "批量检索",
        desc: "异步批量任务提交",
        roles: ["admin", "dev", "user", "service"],
      },
      {
        path: "/app/tasks",
        label: "任务监控",
        desc: "状态查询 · 结果导出",
        roles: ["admin", "service", "readonly", "auditor"],
      },
    ],
  },
  {
    id: "analytics",
    title: "可视化与分析",
    subtitle: "从 UMAP 散点到性能指标的多维分析",
    tone: "violet",
    links: [
      {
        path: "/app/visualization",
        label: "UMAP 可视化",
        desc: "交互散点 · 高亮邻域",
        roles: ["admin", "dev", "user", "readonly", "auditor"],
      },
      {
        path: "/app/metrics",
        label: "性能指标",
        desc: "延迟 · 召回率 · QPS",
        roles: ["admin", "dev", "auditor"],
      },
      {
        path: "/app/reports",
        label: "诊断报告",
        desc: "系统质量诊断报告",
        roles: ["admin", "user", "auditor"],
      },
    ],
  },
  {
    id: "admin",
    title: "平台管理",
    subtitle: "用户与权限的精细化管理",
    tone: "teal",
    links: [
      {
        path: "/app/users",
        label: "用户管理",
        desc: "账号 · 角色 · 权限",
        roles: ["admin"],
      },
    ],
  },
];

const ROLE_WELCOME: Record<
  string,
  { title: string; desc: string; tag: string }
> = {
  admin: {
    title: "系统管理员工作台",
    desc: "掌控全系统能力：用户、数据库、索引与运维。",
    tag: "管理员",
  },
  dev: {
    title: "研发工程师工作台",
    desc: "专注索引构建、ANN 算法调优与性能基准评估。",
    tag: "研发",
  },
  user: {
    title: "业务用户工作台",
    desc: "聚焦临床诊断、实验分析与单细胞检索可视化。",
    tag: "业务",
  },
  service: {
    title: "API 服务账号",
    desc: "通过接口执行程序化检索与批量任务调度。",
    tag: "服务",
  },
  readonly: {
    title: "只读观察账号",
    desc: "浏览数据集、检索结果与可视化内容。",
    tag: "只读",
  },
  auditor: {
    title: "审计评估账号",
    desc: "查阅性能指标、诊断报告与任务执行记录。",
    tag: "审计",
  },
};

function greeting() {
  const h = new Date().getHours();
  if (h < 6) return "夜深了";
  if (h < 12) return "早上好";
  if (h < 14) return "中午好";
  if (h < 18) return "下午好";
  return "晚上好";
}

function useTicker(intervalMs = 1000) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

export function DashboardPage() {
  const { user, token, baseUrl } = useAuth();
  const role = user?.role ?? "";
  const welcome = ROLE_WELCOME[role] ?? {
    title: "欢迎使用",
    desc: "请从下方面板选择功能模块。",
    tag: role || "访客",
  };
  const now = useTicker(1000);

  const [dsCount, setDsCount] = useState<number | null>(null);
  const [idxCount, setIdxCount] = useState<number | null>(null);
  const [idxLoaded, setIdxLoaded] = useState<number | null>(null);
  const [recentDs, setRecentDs] = useState<DatasetItem[]>([]);
  const [recentIdx, setRecentIdx] = useState<IndexItem[]>([]);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [ds, idx] = await Promise.all([
          apiCall<{ list: DatasetItem[]; total: number }>({
            baseUrl,
            token,
            path: "/datasets",
            query: { page: 1, page_size: 5 },
          }).catch(() => null),
          apiCall<{ list: IndexItem[]; total: number }>({
            baseUrl,
            token,
            path: "/indexes",
            query: { page: 1, page_size: 5 },
          }).catch(() => null),
        ]);
        if (cancelled) return;
        if (ds) {
          setDsCount(ds.data.total ?? ds.data.list?.length ?? 0);
          setRecentDs(ds.data.list ?? []);
        }
        if (idx) {
          setIdxCount(idx.data.total ?? idx.data.list?.length ?? 0);
          setRecentIdx(idx.data.list ?? []);
          setIdxLoaded(
            (idx.data.list ?? []).filter((it) => it.is_loaded).length,
          );
        }
        if (!ds && !idx) setLoadFailed(true);
      } catch {
        if (!cancelled) setLoadFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [baseUrl, token]);

  const visibleGroups = useMemo(() => {
    return LINK_GROUPS.map((g) => ({
      ...g,
      links: g.links.filter((l) => !l.roles || l.roles.includes(role)),
    })).filter((g) => g.links.length > 0);
  }, [role]);

  const totalLinks = visibleGroups.reduce((acc, g) => acc + g.links.length, 0);

  const dateLabel = now.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
  const timeLabel = now.toLocaleTimeString("zh-CN", { hour12: false });

  return (
    <div className="dash-root">
      {/* Hero */}
      <section className="dash-hero">
        <div className="dash-hero-main">
          <div className="dash-hero-eyebrow">
            <span className="dash-hero-dot" />
            ANN Retrieval System
            <span className="dash-hero-divider" />
            {dateLabel}
          </div>
          <h2 className="dash-hero-title">
            {greeting()}，{user?.username ?? "研究员"}
          </h2>
          <p className="dash-hero-sub">
            {welcome.title} · {welcome.desc}
          </p>
          <div className="dash-hero-meta">
            <span className="dash-chip">角色 · {welcome.tag}</span>
            <span className="dash-chip dash-chip-ghost">
              UID · {user?.user_id ?? "-"}
            </span>
            <span className="dash-chip dash-chip-ghost">
              {user?.username ?? "-"}
            </span>
          </div>
        </div>
        <div className="dash-hero-clock" aria-hidden="true">
          <div className="dash-clock-face">
            <span className="dash-clock-time">{timeLabel}</span>
            <span className="dash-clock-tz">
              本地时区 · UTC
              {-new Date().getTimezoneOffset() / 60 >= 0 ? "+" : ""}
              {-new Date().getTimezoneOffset() / 60}
            </span>
          </div>
          <div className="dash-clock-orbit" />
          <div className="dash-clock-orbit dash-clock-orbit-2" />
        </div>
      </section>

      {/* KPI */}
      <section className="kpi-row">
        <KpiTile
          tone="teal"
          label="数据集"
          value={dsCount}
          unit="个"
          hint={loadFailed ? "加载失败" : "已纳管的数据集总数"}
          spark={recentDs.map((d) => d.cell_count ?? 0)}
        />
        <KpiTile
          tone="blue"
          label="索引"
          value={idxCount}
          unit="个"
          hint="ANN 索引（含历史版本）"
          spark={recentIdx.map(
            (i) => Number(i.recall_score ?? i.recall ?? 0) * 100,
          )}
        />
        <KpiTile
          tone="amber"
          label="已加载索引"
          value={idxLoaded}
          unit="个"
          hint="可立即提供检索服务"
          ratio={idxCount ? (idxLoaded ?? 0) / Math.max(idxCount, 1) : null}
        />
        <KpiTile
          tone="violet"
          label="可用模块"
          value={totalLinks}
          unit="项"
          hint={`基于角色 ${welcome.tag} 的访问范围`}
        />
      </section>

      {/* Main grid */}
      <section className="dash-grid">
        <div className="dash-grid-main">
          {visibleGroups.map((group) => (
            <div
              key={group.id}
              className={`dash-section dash-tone-${group.tone}`}
            >
              <header className="dash-section-head">
                <div>
                  <span className="dash-section-kicker">{group.title}</span>
                  <p className="dash-section-sub">{group.subtitle}</p>
                </div>
                <span className="dash-section-count">{group.links.length}</span>
              </header>
              <div className="dash-section-grid">
                {group.links.map((link, i) => (
                  <Link
                    key={link.path}
                    to={link.path}
                    className="dash-link-card"
                  >
                    <span className="dash-link-index">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="dash-link-body">
                      <strong>{link.label}</strong>
                      <p>{link.desc}</p>
                    </span>
                    <span className="dash-link-arrow" aria-hidden="true">
                      →
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>

        <aside className="dash-grid-side">
          <div className="dash-rail-card">
            <header className="dash-rail-head">
              <span className="dash-rail-kicker">最近数据集</span>
              <Link to="/app/datasets" className="dash-rail-more">
                查看全部 →
              </Link>
            </header>
            {recentDs.length ? (
              <ul className="dash-rail-list">
                {recentDs.slice(0, 4).map((d) => (
                  <li key={d.dataset_id}>
                    <span className="dash-rail-id">#{d.dataset_id}</span>
                    <span className="dash-rail-name" title={d.dataset_name}>
                      {d.dataset_name ?? "-"}
                    </span>
                    <span className="dash-rail-meta">
                      {(d.cell_count ?? 0).toLocaleString()} 细胞
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="dash-rail-empty">
                {loadFailed ? "暂无权限或服务未连接" : "暂无数据"}
              </p>
            )}
          </div>

          <div className="dash-rail-card">
            <header className="dash-rail-head">
              <span className="dash-rail-kicker">最近索引</span>
              <Link to="/app/indexes" className="dash-rail-more">
                查看全部 →
              </Link>
            </header>
            {recentIdx.length ? (
              <ul className="dash-rail-list">
                {recentIdx.slice(0, 4).map((i) => (
                  <li key={i.index_id}>
                    <span className="dash-rail-id">#{i.index_id}</span>
                    <span className="dash-rail-name" title={i.index_name}>
                      {i.index_name ?? "-"}
                    </span>
                    <span
                      className={`dash-rail-tag dash-rail-tag-${i.is_loaded ? "on" : "off"}`}
                    >
                      {i.is_loaded
                        ? "已加载"
                        : (i.build_status ?? i.status ?? "-")}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="dash-rail-empty">
                {loadFailed ? "暂无权限或服务未连接" : "暂无数据"}
              </p>
            )}
          </div>

          <div className="dash-rail-card dash-rail-tip">
            <span className="dash-rail-kicker">操作小贴士</span>
            <p>
              数据集与索引 ID 在跨页面切换时会通过浏览器本地缓存同步。
              首次部署请在后端运行 <code>scripts/bootstrap_admin.py</code>{" "}
              初始化管理员账号。
            </p>
          </div>
        </aside>
      </section>
    </div>
  );
}

function KpiTile({
  tone,
  label,
  value,
  unit,
  hint,
  spark,
  ratio,
}: {
  tone: "teal" | "blue" | "amber" | "violet";
  label: string;
  value: number | null;
  unit: string;
  hint: string;
  spark?: number[];
  ratio?: number | null;
}) {
  const display = value === null ? "—" : value.toLocaleString();
  return (
    <div className={`kpi-tile kpi-tone-${tone}`}>
      <div className="kpi-head">
        <span className="kpi-label">{label}</span>
        <span className="kpi-glyph" aria-hidden="true" />
      </div>
      <div className="kpi-value-row">
        <strong className="kpi-value">{display}</strong>
        <span className="kpi-unit">{unit}</span>
      </div>
      <p className="kpi-hint">{hint}</p>
      {typeof ratio === "number" && (
        <div className="kpi-bar">
          <span
            style={{
              width: `${Math.round(Math.min(1, Math.max(0, ratio)) * 100)}%`,
            }}
          />
        </div>
      )}
      {spark && spark.length > 0 && <Sparkline values={spark} />}
    </div>
  );
}

function Sparkline({ values }: { values: number[] }) {
  const safe = values.filter((v) => Number.isFinite(v));
  if (safe.length < 2) return <div className="kpi-spark-placeholder" />;
  const max = Math.max(...safe, 1);
  const min = Math.min(...safe, 0);
  const range = max - min || 1;
  const W = 120;
  const H = 28;
  const step = W / (safe.length - 1);
  const points = safe
    .map((v, i) => {
      const x = i * step;
      const y = H - ((v - min) / range) * (H - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      className="kpi-spark"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <polyline points={points} fill="none" strokeWidth="1.6" />
    </svg>
  );
}
