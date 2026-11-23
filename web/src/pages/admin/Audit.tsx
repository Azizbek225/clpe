import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { Spinner } from "../../components/ui";

export default function Audit() {
  const [filter, setFilter] = useState("");
  const { data, loading } = useApi<any[]>(`/admin/audit?limit=300${filter ? `&action=${encodeURIComponent(filter)}` : ""}`, [filter]);
  return (
    <div className="space-y-4">
      <input className="input max-w-xs font-mono" placeholder="action prefix: lab., auth., course." value={filter} onChange={(e) => setFilter(e.target.value)} />
      {loading ? <Spinner /> : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <tbody>
              {data?.map((a) => (
                <tr key={a.id} className="border-t border-edge">
                  <td className="px-3 py-2 text-muted whitespace-nowrap">{new Date(a.created_at).toLocaleString()}</td>
                  <td className="px-3 py-2 text-cyber">{a.username ?? "—"}</td>
                  <td className={`px-3 py-2 ${a.action.includes("failed") ? "text-threat" : "text-neon"}`}>{a.action}</td>
                  <td className="px-3 py-2 text-slate-400">{a.resource_type}:{a.resource_id}</td>
                  <td className="px-3 py-2 text-muted">{a.ip}</td>
                  <td className="px-3 py-2 text-slate-500 truncate max-w-xs">{a.details}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
