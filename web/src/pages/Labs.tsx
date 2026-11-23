import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Clock, FlaskConical, Server, Swords, Shield, Target } from "lucide-react";
import { useApi } from "../hooks/useApi";
import type { LabSummary } from "../api/types";
import { Difficulty, PageHeader, Spinner, StatusPill } from "../components/ui";

const TYPE_ICON: Record<string, any> = { offensive: Swords, defensive: Shield, forensics: Target };

export default function Labs() {
  const { t, i18n } = useTranslation();
  const { data, loading } = useApi<LabSummary[]>(`/labs?lang=${i18n.language}`, [i18n.language]);
  const [cat, setCat] = useState<string>("all");
  if (loading) return <Spinner />;
  const cats = ["all", ...new Set((data ?? []).map((l) => l.category))];
  const list = (data ?? []).filter((l) => cat === "all" || l.category === cat);
  return (
    <div>
      <PageHeader title={t("labs.title")} subtitle={t("labs.subtitle")} icon={<FlaskConical />} />
      <div className="flex flex-wrap gap-2 mb-5">
        {cats.map((c) => (
          <button key={c} onClick={() => setCat(c)} className={`chip px-3 py-1 ${cat === c ? "text-neon border-neon/50 bg-neon/10" : "text-muted border-edge hover:text-slate-200"}`}>
            {c}
          </button>
        ))}
      </div>
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {list.map((l) => {
          const Icon = TYPE_ICON[l.lab_type] ?? FlaskConical;
          return (
            <Link key={l.id} to={`/labs/${l.id}`} className="panel panel-hover p-5 flex flex-col relative overflow-hidden">
              <div className="absolute -right-6 -top-6 opacity-[0.06]"><Icon size={120} /></div>
              <div className="flex items-center justify-between">
                <span className={`chip ${l.lab_type === "defensive" ? "text-cyber border-cyber/40" : "text-threat border-threat/40"}`}>
                  <Icon size={11} /> {l.lab_type}
                </span>
                <Difficulty level={l.difficulty} />
              </div>
              <h3 className="mt-3 text-lg text-slate-100">{l.title}</h3>
              <p className="text-sm text-muted mt-1 flex-1">{l.description}</p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 mt-4 text-xs font-mono text-muted whitespace-nowrap">
                <span className="flex items-center gap-1"><Server size={13} /> {l.machines} {t("labs.machines")}</span>
                <span>{l.tasks} {t("labs.tasks")}</span>
                <span className="flex items-center gap-1"><Clock size={13} /> {l.duration_minutes} {t("common.minutes")}</span>
                <span className="text-warn">{l.points} {t("common.points")}</span>
              </div>
              <div className="mt-3 flex items-center justify-between text-[11px] font-mono text-muted">
                <span>{l.category} · v{l.version}</span>
                {l.active_instance && <StatusPill status={l.active_instance.status} />}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
