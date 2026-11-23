import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, FlaskConical } from "lucide-react";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import { ErrorBox, Markdown, Spinner, toast } from "../components/ui";

export default function Lesson() {
  const { id } = useParams();
  const nav = useNavigate();
  const { t, i18n } = useTranslation();
  const { data: le, loading, error, reload } = useApi<any>(`/lessons/${id}?lang=${i18n.language}`, [id, i18n.language]);
  if (loading) return <Spinner />;
  if (!le) return <ErrorBox msg={error} />;

  const complete = async () => {
    const r = await api(`/lessons/${le.id}/complete`, { method: "POST" });
    toast(r.certificate ? `${t("quiz.certificate")}: ${r.certificate.number}` : "+10 XP");
    if (le.next_id) nav(`/lessons/${le.next_id}`);
    else reload();
  };

  return (
    <div className="max-w-4xl">
      <Link to={`/courses/${le.course_id}`} className="text-sm text-muted hover:text-neon font-mono">← {le.module_title}</Link>
      <article className="panel p-8 mt-3">
        <div className="flex items-center gap-3 mb-6 text-xs font-mono text-muted">
          <span className="chip text-cyber border-cyber/40">{le.lesson_type}</span>
          <span>{le.duration} {t("common.minutes")}</span>
          {le.completed && <span className="text-neon flex items-center gap-1"><CheckCircle2 size={14} /> {t("lesson.completed")}</span>}
        </div>
        <h1 className="font-mono text-2xl text-slate-100 mb-6">{le.title}</h1>
        {le.video_url && (
          <div className="mb-6 aspect-video rounded-lg overflow-hidden border border-edge">
            <iframe src={le.video_url} className="w-full h-full" allowFullScreen title={le.title} />
          </div>
        )}
        <Markdown text={le.content} />
        {le.lab_slug && (
          <Link to={`/labs/${le.lab_slug}`} className="btn-cyber mt-4">
            <FlaskConical size={16} /> {t("lesson.openLab")}
          </Link>
        )}
      </article>
      <div className="flex justify-between mt-4">
        <button className="btn-ghost" disabled={!le.prev_id} onClick={() => nav(`/lessons/${le.prev_id}`)}>← {t("common.prev")}</button>
        <button className="btn-primary" onClick={complete}>
          {le.completed ? t("common.next") : t("lesson.complete")} →
        </button>
      </div>
    </div>
  );
}
