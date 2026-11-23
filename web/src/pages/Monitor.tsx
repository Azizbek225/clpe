import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MonitorDot } from "lucide-react";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useAuth } from "../hooks/useAuth";
import { Empty, PageHeader, Spinner, StatusPill, toast } from "../components/ui";

export default function Monitor() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const { data, loading, reload } = useApi<any[]>("/labs/instances");
  if (loading) return <Spinner />;
  const stop = async (id: string) => {
    await api(`/admin/instances/${id}/stop`, { method: "POST" });
    toast("stopped");
    reload();
  };
  return (
    <div>
      <PageHeader title={t("monitor.title")} icon={<MonitorDot />} actions={<button className="btn-ghost" onClick={reload}>↻</button>} />
      <div className="panel overflow-x-auto">
        {!data?.length ? <Empty /> : (
          <table className="w-full text-sm">
            <thead className="text-left font-mono text-xs text-muted uppercase">
              <tr>{["user", "lab", t("common.status"), t("labs.score"), "provider", "VM", "started", ""].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}</tr>
            </thead>
            <tbody>
              {data.map((i) => (
                <tr key={i.id} className="border-t border-edge">
                  <td className="px-4 py-2.5 font-mono text-cyber">{i.username}</td>
                  <td className="px-4 py-2.5"><Link className="hover:text-neon" to={`/labs/${i.lab}`}>{i.title}</Link></td>
                  <td className="px-4 py-2.5"><StatusPill status={i.status} /></td>
                  <td className="px-4 py-2.5 font-mono text-warn">{i.score}</td>
                  <td className="px-4 py-2.5 font-mono text-muted">{i.provider}</td>
                  <td className="px-4 py-2.5 font-mono">{i.machines}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-muted">{i.started_at ? new Date(i.started_at).toLocaleString() : "—"}</td>
                  <td className="px-4 py-2.5">{can("labs:manage") && i.status === "RUNNING" && <button className="btn-danger py-1 px-2 text-xs" onClick={() => stop(i.id)}>stop</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
