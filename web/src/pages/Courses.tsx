import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BookOpen, Clock, FlaskConical, Layers } from "lucide-react";
import { useApi } from "../hooks/useApi";
import type { CourseSummary } from "../api/types";
import { Difficulty, ErrorBox, PageHeader, Progress, Spinner } from "../components/ui";

export default function Courses() {
  const { t, i18n } = useTranslation();
  const { data, loading, error } = useApi<CourseSummary[]>(`/courses?lang=${i18n.language}&include_drafts=true`, [i18n.language]);
  if (loading) return <Spinner />;
  return (
    <div>
      <PageHeader title={t("courses.title")} icon={<BookOpen />} />
      <ErrorBox msg={error} />
      <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {data?.map((c) => {
          const draft = c.status !== "published";
          return (
            <Link key={c.id} to={`/courses/${c.slug}`} className={`panel panel-hover p-5 flex flex-col ${draft ? "opacity-60" : ""}`}>
              <div className="flex items-start justify-between">
                <span className="font-mono text-3xl text-neon/80 glow-text">{c.code}</span>
                {draft ? <span className="chip text-muted border-edge">{t("courses.draft")}</span> : <Difficulty level={c.difficulty} />}
              </div>
              <h3 className="mt-3 text-lg text-slate-100">{c.title}</h3>
              <p className="text-sm text-muted mt-1 flex-1">{c.description}</p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 mt-4 text-xs font-mono text-muted whitespace-nowrap">
                <span className="flex items-center gap-1"><Layers size={13} /> {c.modules} {t("courses.modules")}</span>
                <span className="flex items-center gap-1"><BookOpen size={13} /> {c.lessons} {t("courses.lessons")}</span>
                <span className="flex items-center gap-1"><FlaskConical size={13} /> {c.labs} {t("courses.labs")}</span>
                {c.estimated_duration > 0 && <span className="flex items-center gap-1"><Clock size={13} /> {Math.round(c.estimated_duration / 60)}h</span>}
              </div>
              {!draft && <div className="mt-3"><Progress value={c.progress} /></div>}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
