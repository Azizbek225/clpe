import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { PageHeader } from "../../components/ui";
import Overview from "./Overview";
import ContentEditor from "./ContentEditor";
import LabEditor from "./LabEditor";
import Users from "./Users";
import Engine from "./Engine";
import Audit from "./Audit";

export default function Admin() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const tabs = [
    can("reports:read") && ["overview", t("admin.overview")],
    can("content:write") && ["content", t("admin.content")],
    can("labs:author") && ["labs", t("admin.labs")],
    can("users:manage") && ["users", t("admin.users")],
    can("labs:author") && ["engine", t("admin.engine")],
    can("audit:read") && ["audit", t("admin.audit")],
  ].filter(Boolean) as [string, string][];
  return (
    <div>
      <PageHeader title={t("nav.admin")} icon={<ShieldCheck />} />
      <div className="flex flex-wrap border-b border-edge mb-6">
        {tabs.map(([k, label]) => (
          <NavLink key={k} to={`/admin/${k}`} className={({ isActive }) => `tab ${isActive ? "tab-active" : ""}`}>{label}</NavLink>
        ))}
      </div>
      <Routes>
        <Route index element={<Navigate to={tabs[0]?.[0] ?? "content"} replace />} />
        <Route path="overview" element={<Overview />} />
        <Route path="content" element={<ContentEditor />} />
        <Route path="labs" element={<LabEditor />} />
        <Route path="users" element={<Users />} />
        <Route path="engine" element={<Engine />} />
        <Route path="audit" element={<Audit />} />
      </Routes>
    </div>
  );
}
