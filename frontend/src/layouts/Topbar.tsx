import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const ROLE_LABELS: Record<string, string> = {
  admin: "系统管理员",
  dev: "研发人员",
  user: "业务用户",
  service: "服务账号",
  readonly: "只读观察",
  auditor: "审计人员",
};

export function Topbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <header className="app-topbar">
      <div className="topbar-left">
        <span className="topbar-title">ANN Retrieval System</span>
      </div>
      <div className="topbar-right">
        {user && (
          <>
            <span className="topbar-username">{user.username}</span>
            <span className="role-tag">
              {ROLE_LABELS[user.role] ?? user.role}
            </span>
          </>
        )}
        <button
          className="btn btn-secondary topbar-logout"
          type="button"
          onClick={handleLogout}
        >
          退出登录
        </button>
      </div>
    </header>
  );
}
