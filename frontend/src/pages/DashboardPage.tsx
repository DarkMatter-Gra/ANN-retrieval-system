import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

type QuickLink = { path: string; label: string; desc: string; roles?: string[] };

const QUICK_LINKS: QuickLink[] = [
  { path: '/app/clinical', label: '临床诊断工作台', desc: '查询相似细胞、生成诊断参考报告', roles: ['user', 'admin'] },
  { path: '/app/experiment', label: '实验分析工作台', desc: '预处理监控、质控与表型检索', roles: ['user', 'admin'] },
  { path: '/app/bioinfo', label: 'API 接入工作台', desc: '程序化检索接口与批量任务管理', roles: ['service', 'admin'] },
  { path: '/app/research', label: '研发工作台', desc: '索引构建、算法调优与性能评估', roles: ['dev', 'admin'] },
  { path: '/app/database', label: '数据库管理', desc: '公共数据集导入、版本与权限管理', roles: ['admin'] },
  { path: '/app/ops', label: '系统运维', desc: '服务监控、资源调度与告警管理', roles: ['admin'] },
  { path: '/app/datasets', label: '数据集管理', desc: '上传并管理单细胞基因组数据集', roles: ['admin', 'dev', 'user', 'readonly', 'auditor'] },
  { path: '/app/indexes', label: '索引管理', desc: '创建和管理 ANN 向量索引', roles: ['admin', 'dev'] },
  { path: '/app/search', label: '向量检索', desc: '执行单次近似最近邻检索', roles: ['admin', 'dev', 'user', 'service', 'readonly'] },
  { path: '/app/batch-search', label: '批量检索', desc: '提交异步批量检索任务', roles: ['admin', 'dev', 'user', 'service'] },
  { path: '/app/tasks', label: '任务监控', desc: '查询任务状态、导出检索结果', roles: ['admin', 'service', 'readonly', 'auditor'] },
  { path: '/app/visualization', label: 'UMAP 可视化', desc: '交互式 UMAP/t-SNE 散点图', roles: ['admin', 'dev', 'user', 'readonly', 'auditor'] },
  { path: '/app/metrics', label: '性能指标', desc: '检索延迟、召回率统计分析', roles: ['admin', 'dev', 'auditor'] },
  { path: '/app/reports', label: '诊断报告', desc: '系统质量诊断与健康报告', roles: ['admin', 'user', 'auditor'] },
  { path: '/app/users', label: '用户管理', desc: '管理系统用户账号与权限', roles: ['admin'] },
];

const ROLE_WELCOME: Record<string, { title: string; desc: string }> = {
  admin: { title: '系统管理员工作台', desc: '您拥有全部系统权限，可管理用户、数据库与系统运维。' },
  dev: { title: '研发工程师工作台', desc: '专注于索引构建、ANN 算法调优与性能基准评估。' },
  user: { title: '业务用户工作台', desc: '支持临床诊断、实验分析与单细胞检索可视化。' },
  service: { title: 'API 服务账号', desc: '通过 API 接口执行程序化检索与批量任务。' },
  readonly: { title: '只读观察账号', desc: '浏览数据集、检索结果与可视化内容。' },
  auditor: { title: '审计评估账号', desc: '查阅性能指标、诊断报告与任务记录。' },
};

export function DashboardPage() {
  const { user } = useAuth();
  const role = user?.role ?? '';
  const welcome = ROLE_WELCOME[role] ?? { title: '欢迎使用', desc: '请从左侧导航选择功能模块。' };
  const visible = QUICK_LINKS.filter((l) => !l.roles || l.roles.includes(role));

  return (
    <div className="page-container">
      <div className="page-header">
        <p className="eyebrow">ANN Retrieval System</p>
        <h2>{welcome.title}</h2>
        <p className="hero-copy">{welcome.desc}</p>
      </div>

      {user && (
        <div className="hero-cards" style={{ marginBottom: '0.5rem' }}>
          <article className="mini-card">
            <span>用户名</span>
            <strong>{user.username}</strong>
          </article>
          <article className="mini-card">
            <span>角色</span>
            <strong>{user.role}</strong>
          </article>
          <article className="mini-card">
            <span>用户 ID</span>
            <strong>{user.user_id}</strong>
          </article>
        </div>
      )}

      <div className="feature-grid">
        {visible.map((link) => (
          <Link key={link.path} to={link.path} className="feature-card">
            <strong>{link.label}</strong>
            <p>{link.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
