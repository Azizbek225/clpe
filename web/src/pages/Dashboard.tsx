import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Award, Cpu, FlaskConical, Zap } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useApi } from "../hooks/useApi";
import type { LabSummary } from "../api/types";
import { Empty, PageHeader, Progress, Stat, StatusPill } from "../components/ui";

type ProgressData = {
  xp: number; level: number; next_level_xp: number; lab_points: number;
  courses: { course_id: string; slug: string; title: string; completed: number; total: number; percent: number }[];
};

export default function Dashboard() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const { data: prog } = useApi<ProgressData>("/progress");
  const { data: labs } = useApi<LabSummary[]>(`/labs?lang=${i18n.language}`, [i18n.language]);
  const { data: certs } = useApi<any[]>("/certificates");
  const active = (labs ?? []).filter((l) => l.active_instance);

  return (
    <div>
      <PageHeader title={`${t("dash.welcome")}, ${user?.full_name || user?.username}`} subtitle={t("app.tagline")} />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Stat label={t("dash.level")} value={`LVL ${prog?.level ?? user?.level}`} icon={<Zap size={16} />} />
        <Stat label="XP" value={prog?.xp ?? user?.xp ?? 0} icon={<Cpu size={16} />} accent="text-cyber" />
        <Stat label={t("dash.labPoints")} value={prog?.lab_points ?? 0} icon={<FlaskConical size={16} />} accent="text-warn" />
        <Stat label={t("dash.certificates")} value={certs?.length ?? 0} icon={<Award size={16} />} accent="text-violet" />
      </div>
      {prog && (
        <div className="panel p-4 mb-6">
          <div className="flex justify-between text-xs font-mono text-muted mb-2">
            <span>LVL {prog.level}</span>
            <span>{prog.next_level_xp - prog.xp} XP {t("dash.xpToNext")}</span>
          </div>
          <Progress value={((prog.xp % 500) / 500) * 100} color="cyber" />
        </div>
      )}
      <div className="grid lg:grid-cols-2 gap-6">
        <section className="panel p-5">
          <h2 className="font-mono text-cyber mb-4">{t("dash.myCourses")}</h2>
          <div className="space-y-4">
            {prog?.courses.filter((c) => c.total > 0).map((c) => (
              <Link key={c.course_id} to={`/courses/${c.slug}`} className="block group">
                <div className="flex justify-between text-sm mb-1.5">
                  <span className="group-hover:text-neon">{c.title}</span>
                  <span className="font-mono text-muted">{c.completed}/{c.total}</span>
                </div>
                <Progress value={c.percent} />
              </Link>
            ))}
          </div>
        </section>
        <section className="panel p-5">
          <h2 className="font-mono text-cyber mb-4">{t("dash.activeLabs")}</h2>
          {active.length === 0 ? (
            <Empty>
              <Link to="/labs" className="btn-primary mt-2">{t("nav.labs")} →</Link>
            </Empty>
          ) : (
            <div className="space-y-3">
              {active.map((l) => (
                <Link key={l.id} to={`/labs/${l.id}`} className="flex items-center justify-between panel panel-hover px-4 py-3">
                  <span>{l.title}</span>
                  <StatusPill status={l.active_instance!.status} />
                </Link>
              ))}
            </div>
          )}
          {certs && certs.length > 0 && (
            <div className="mt-6">
              <h3 className="font-mono text-violet text-sm mb-2">{t("dash.certificates")}</h3>
              {certs.map((c) => (
                <div key={c.number} className="text-sm flex justify-between border-t border-edge py-2">
                  <span>{c.course}</span>
                  <span className="font-mono text-violet">{c.number}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
