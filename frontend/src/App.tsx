import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { RoleRoute } from "./auth/RoleRoute";
import { AppLayout } from "./layouts/AppLayout";
import { AiSearchPage } from "./pages/AiSearchPage";
import { BatchSearchPage } from "./pages/BatchSearchPage";
import { BioinfoPage } from "./pages/BioinfoPage";
import { ClinicalPage } from "./pages/ClinicalPage";
import { DatabasePage } from "./pages/DatabasePage";
import { DashboardPage } from "./pages/DashboardPage";
import { DatasetsPage } from "./pages/DatasetsPage";
import { ExperimentPage } from "./pages/ExperimentPage";
import { IndexesPage } from "./pages/IndexesPage";
import { LoginPage } from "./pages/LoginPage";
import { MetricsPage } from "./pages/MetricsPage";
import { OpsPage } from "./pages/OpsPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ResearchPage } from "./pages/ResearchPage";
import { SearchPage } from "./pages/SearchPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TasksPage } from "./pages/TasksPage";
import { UsersPage } from "./pages/UsersPage";
import { VisualizationPage } from "./pages/VisualizationPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected: requires authentication */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            {/* All authenticated roles */}
            <Route path="/app/dashboard" element={<DashboardPage />} />
            <Route path="/app/search" element={<SearchPage />} />
            <Route path="/app/ai-search" element={<AiSearchPage />} />
            <Route path="/app/visualization" element={<VisualizationPage />} />
            <Route path="/app/settings" element={<SettingsPage />} />

            {/* Datasets: all except service */}
            <Route
              element={
                <RoleRoute
                  roles={["admin", "dev", "user", "readonly", "auditor"]}
                />
              }
            >
              <Route path="/app/datasets" element={<DatasetsPage />} />
            </Route>

            {/* Batch search: all except readonly, auditor */}
            <Route
              element={
                <RoleRoute roles={["admin", "dev", "user", "service"]} />
              }
            >
              <Route path="/app/batch-search" element={<BatchSearchPage />} />
            </Route>

            {/* Tasks: admin, service, readonly, auditor */}
            <Route
              element={
                <RoleRoute
                  roles={["admin", "service", "readonly", "auditor"]}
                />
              }
            >
              <Route path="/app/tasks" element={<TasksPage />} />
            </Route>

            {/* Indexes: admin, dev */}
            <Route element={<RoleRoute roles={["admin", "dev"]} />}>
              <Route path="/app/indexes" element={<IndexesPage />} />
            </Route>

            {/* Metrics: admin, dev, auditor */}
            <Route element={<RoleRoute roles={["admin", "dev", "auditor"]} />}>
              <Route path="/app/metrics" element={<MetricsPage />} />
            </Route>

            {/* Reports: admin, user, auditor */}
            <Route element={<RoleRoute roles={["admin", "user", "auditor"]} />}>
              <Route path="/app/reports" element={<ReportsPage />} />
            </Route>

            {/* Users: admin only */}
            <Route element={<RoleRoute roles={["admin"]} />}>
              <Route path="/app/users" element={<UsersPage />} />
            </Route>

            {/* Clinical / Experiment: user + admin */}
            <Route element={<RoleRoute roles={["admin", "user"]} />}>
              <Route path="/app/clinical" element={<ClinicalPage />} />
              <Route path="/app/experiment" element={<ExperimentPage />} />
            </Route>

            {/* Bioinfo: service + admin */}
            <Route element={<RoleRoute roles={["admin", "service"]} />}>
              <Route path="/app/bioinfo" element={<BioinfoPage />} />
            </Route>

            {/* Research: dev + admin */}
            <Route element={<RoleRoute roles={["admin", "dev"]} />}>
              <Route path="/app/research" element={<ResearchPage />} />
            </Route>

            {/* Database / Ops: admin only */}
            <Route element={<RoleRoute roles={["admin"]} />}>
              <Route path="/app/database" element={<DatabasePage />} />
              <Route path="/app/ops" element={<OpsPage />} />
            </Route>
          </Route>
        </Route>

        {/* Default redirect */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </AuthProvider>
  );
}
