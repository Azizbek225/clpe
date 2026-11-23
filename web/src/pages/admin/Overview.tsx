import { useTranslation } from "react-i18next";
import { Activity, AlertTriangle, Cpu, FlaskConical, MemoryStick, Server, ShieldAlert, Users } from "lucide-react";
import { useApi } from "../../hooks/useApi";
import { Progress, Spinner, Stat, StatusPill } from "../../components/ui";

export default function Overview() {
  const { t } = useTranslation();
  const { data: d } = useApi<any>("/admin/dashboard");
  const { data: errs } = useApi<any[]>("/admin/lab-errors");
  if (!d) return <Spinner />;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label={t("stat.users")} value={d.users_total} icon={<Users size={16} />} />
        <Stat label={t("stat.active24")} value={d.users_active_24h} icon={<Activity size={16} />} accent="text-cyber" />
        <Stat label={t("stat.labsActive")} value={d.labs_active} icon={<FlaskConical size={16} />} accent="text-warn" />
        <Stat label={t("stat.vms")} value={d.vms_running} icon={<Server size={16} />} accent="text-violet" />
        <Stat label={t("stat.cpu")} value={`${d.cpu_allocated_pct}%`} icon={<Cpu size={16} />} accent="text-cyber" />
        <Stat label={t("stat.ram")} value={`${d.ram_allocated_pct}%`} icon={<MemoryStick size={16} />} accent="text-cyber" />
        <Stat label={t("stat.labErrors")} value={d.lab_errors_24h} icon={<AlertTriangle size={16} />} accent="text-threat" />
        <Stat label={t("stat.security")} value={d.security_events_24h} icon={<ShieldAlert size={16} />} accent="text-threat" />
      </div>
      <div className="grid lg:grid-cols-2 gap-6">
        <section className="panel p-5">
          <h3 className="font-mono text-cyber mb-4">Lab instances</h3>
          <div className="space-y-3">
            {Object.entries(d.labs_by_status as Record<string, number>).map(([s, n]) => (
              <div key={s} className="flex items-center gap-3">
                <div className="w-28"><StatusPill status={s} /></div>
                <div className="flex-1"><Progress value={(n / Math.max(1, ...Object.values(d.labs_by_status as Record<string, number>))) * 100} color={s === "ERROR" ? "threat" : "neon"} /></div>
                <span className="font-mono text-sm w-8 text-right">{n}</span>
              </div>
            ))}
          </div>
          <div className="text-xs text-muted font-mono mt-4">provider: <span className="text-neon">{d.provider}</span> · courses: {d.courses} · lab templates: {d.labs_templates}</div>
        </section>
        <section className="panel p-5">
          <h3 className="font-mono text-threat mb-4">{t("stat.labErrors")}</h3>
          <div className="font-mono text-xs space-y-2 max-h-72 overflow-y-auto">
            {(errs ?? []).slice(0, 30).map((e, i) => (
              <div key={i} className="border-t border-edge pt-2"><span className="text-muted">{new Date(e.created_at).toLocaleString()}</span> <span className="text-threat">{JSON.stringify(e.details)}</span></div>
            ))}
            {!errs?.length && <div className="text-muted">—</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
