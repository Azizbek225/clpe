import { useApi } from "../../hooks/useApi";
import { Spinner } from "../../components/ui";

export default function Engine() {
  const { data: d } = useApi<any>("/admin/lab-engine");
  const { data: hosts } = useApi<any[]>("/admin/hosts");
  if (!d) return <Spinner />;
  return (
    <div className="space-y-6">
      <div className="grid md:grid-cols-3 gap-4">
        <div className="panel p-4">
          <div className="label">Active provider</div>
          <div className="font-mono text-2xl text-neon">{d.active_provider}</div>
          <div className={`text-xs font-mono mt-1 ${d.health.ok ? "text-neon" : "text-threat"}`}>{d.health.ok ? "● healthy" : `● ${d.health.error}`}</div>
          <div className="text-xs text-muted mt-2">registered: {d.providers.join(", ")}</div>
        </div>
        <div className="panel p-4">
          <div className="label">Validator plugins</div>
          <div className="flex flex-wrap gap-1">{d.validator_types.map((v: string) => <span key={v} className="chip text-cyber border-cyber/40">{v}</span>)}</div>
        </div>
        <div className="panel p-4">
          <div className="label">Isolation policy</div>
          <div className="text-sm font-mono">bridged: <span className="text-threat">forbidden</span></div>
          <div className="text-sm font-mono">internet labs: <span className={d.allow_internet_labs ? "text-warn" : "text-neon"}>{d.allow_internet_labs ? "allowed" : "blocked"}</span></div>
          <div className="text-sm font-mono">host shell: <span className="text-threat">never</span></div>
        </div>
      </div>
      <section className="panel overflow-x-auto">
        <h3 className="font-mono text-cyber px-4 pt-4">VM / container templates</h3>
        <table className="w-full text-xs font-mono mt-2">
          <thead className="text-muted text-left"><tr>{["slug", "name", "os", "provider", "role", "image", "checksum", "cpu", "ram"].map((h) => <th key={h} className="px-4 py-2">{h}</th>)}</tr></thead>
          <tbody>
            {d.templates.map((t: any) => (
              <tr key={t.slug} className="border-t border-edge">
                <td className="px-4 py-2 text-neon">{t.slug}</td><td className="px-4 py-2">{t.name}</td><td className="px-4 py-2 text-muted">{t.os}</td>
                <td className="px-4 py-2 text-cyber">{t.provider}</td><td className="px-4 py-2">{t.role}</td>
                <td className="px-4 py-2 text-slate-400">{t.image}</td><td className={`px-4 py-2 ${t.checksum ? "text-neon" : "text-warn"}`}>{t.checksum ? "✔" : "unset"}</td>
                <td className="px-4 py-2">{t.cpu}</td><td className="px-4 py-2">{t.ram}MB</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel p-4">
        <h3 className="font-mono text-cyber mb-2">Virtualization hosts</h3>
        {hosts?.map((h) => <div key={h.id} className="font-mono text-sm">{h.hostname} · {h.provider} · {h.cpu} CPU · {h.ram} MB · <span className="text-neon">{h.status}</span></div>)}
      </section>
    </div>
  );
}
