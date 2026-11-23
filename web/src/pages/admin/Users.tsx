import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { ErrorBox, Spinner, toast } from "../../components/ui";

export default function Users() {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const { data, loading, reload } = useApi<any[]>(`/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`, [q]);
  const { data: roles } = useApi<any[]>("/admin/roles");
  const [nu, setNu] = useState({ username: "", email: "", password: "", full_name: "", role: "student" });
  const [err, setErr] = useState<string | null>(null);

  const setRoles = async (u: any, role: string, on: boolean) => {
    const next = on ? [...u.roles, role] : u.roles.filter((r: string) => r !== role);
    try {
      await api(`/admin/users/${u.id}`, { method: "PUT", json: { roles: next } });
      reload();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  const toggleBlock = async (u: any) => {
    await api(`/admin/users/${u.id}`, { method: "PUT", json: { status: u.status === "active" ? "blocked" : "active" } });
    reload();
  };
  const create = async () => {
    setErr(null);
    try {
      await api("/admin/users", { method: "POST", json: { ...nu, roles: [nu.role] } });
      toast(t("common.saved"));
      setNu({ username: "", email: "", password: "", full_name: "", role: "student" });
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  };

  return (
    <div className="space-y-5">
      <div className="panel p-4 grid md:grid-cols-6 gap-2 items-end">
        {(["username", "email", "password", "full_name"] as const).map((k) => (
          <div key={k}><label className="label">{t(`auth.${k === "full_name" ? "fullName" : k}`)}</label>
            <input className="input" type={k === "password" ? "password" : "text"} value={nu[k]} onChange={(e) => setNu({ ...nu, [k]: e.target.value })} /></div>
        ))}
        <div><label className="label">{t("admin.roles")}</label>
          <select className="input" value={nu.role} onChange={(e) => setNu({ ...nu, role: e.target.value })}>
            {roles?.map((r) => <option key={r.name} value={r.name}>{r.description}</option>)}
          </select></div>
        <button className="btn-primary" onClick={create}>{t("common.create")}</button>
        <div className="md:col-span-6"><ErrorBox msg={err} /></div>
      </div>
      <input className="input max-w-xs" placeholder={t("common.search")} value={q} onChange={(e) => setQ(e.target.value)} />
      {loading ? <Spinner /> : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-sm">
            <tbody>
              {data?.map((u) => (
                <tr key={u.id} className="border-t border-edge align-top">
                  <td className="px-4 py-3"><div className="font-mono text-cyber">{u.username}</div><div className="text-xs text-muted">{u.email}</div></td>
                  <td className="px-4 py-3 font-mono text-xs text-warn">{u.xp} XP</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {roles?.map((r) => {
                        const on = u.roles.includes(r.name);
                        return <button key={r.name} onClick={() => setRoles(u, r.name, !on)} title={r.permissions.join(", ")}
                          className={`chip ${on ? "text-neon border-neon/50 bg-neon/10" : "text-muted border-edge hover:text-slate-300"}`}>{r.name}</button>;
                      })}
                    </div>
                  </td>
                  <td className="px-4 py-3"><button className={u.status === "active" ? "btn-ghost text-xs py-1" : "btn-danger text-xs py-1"} onClick={() => toggleBlock(u)}>{u.status}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
