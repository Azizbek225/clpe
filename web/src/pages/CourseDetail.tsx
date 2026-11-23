import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Circle, ClipboardCheck, FileText, FlaskConical, PlayCircle } from "lucide-react";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import type { CourseDetail as CD } from "../api/types";
import { Difficulty, ErrorBox, PageHeader, Progress, Spinner, toast } from "../components/ui";

const ICON: Record<string, any> = { theory: FileText, video: PlayCircle, lab: FlaskConical, quiz: ClipboardCheck };

export default function CourseDetail() {
  const { key } = useParams();
  const { t, i18n } = useTranslation();
  const { data: c, loading, error, reload } = useApi<CD>(`/courses/${key}?lang=${i18n.language}`, [i18n.language]);
  if (loading) return <Spinner />;
  if (!c) return <ErrorBox msg={error} />;

  const enroll = async () => {
    await api(`/courses/${c.slug}/enroll`, { method: "POST" });
    toast(t("courses.enrolled"));
    reload();
  };

  return (
    <div className="max-w-5xl">
      <Link to="/courses" className="text-sm text-muted hover:text-neon font-mono">← {t("nav.courses")}</Link>
      <div className="mt-3">
        <PageHeader
          title={`${c.code} · ${c.title}`}
          subtitle={c.description}
          actions={c.enrolled ? <span className="chip text-neon border-neon/40">{t("courses.enrolled")}</span> : <button className="btn-primary" onClick={enroll}>{t("courses.enroll")}</button>}
        />
      </div>
      <div className="grid md:grid-cols-3 gap-4 mb-6">
        <div className="panel p-4 md:col-span-2">
          <h3 className="label">{t("courses.objectives")}</h3>
          <ul className="space-y-1.5 text-sm">
            {c.objectives?.map((o) => <li key={o} className="flex gap-2"><span className="text-neon">▸</span>{o}</li>)}
          </ul>
        </div>
        <div className="panel p-4 space-y-3">
          <Difficulty level={c.difficulty} />
          <div className="text-3xl font-mono text-neon">{c.progress}%</div>
          <Progress value={c.progress} />
          <div className="text-xs font-mono text-muted">{c.lessons} {t("courses.lessons")} · {c.labs} {t("courses.labs")}</div>
        </div>
      </div>
      <div className="space-y-4">
        {c.modules_detail.map((m) => (
          <section key={m.id} className="panel">
            <header className="px-5 py-4 border-b border-edge flex items-center justify-between">
              <div>
                <div className="text-xs font-mono text-cyber">MODULE {String(m.sequence_number).padStart(2, "0")}</div>
                <h3 className="text-slate-100 text-lg">{m.title}</h3>
                {m.description && <p className="text-sm text-muted">{m.description}</p>}
              </div>
              <Difficulty level={m.level} />
            </header>
            <ul>
              {m.lessons.map((le) => {
                const Icon = ICON[le.lesson_type] ?? FileText;
                return (
                  <li key={le.id}>
                    <Link to={`/lessons/${le.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-white/5 border-b border-edge/50 last:border-0">
                      {le.completed ? <CheckCircle2 size={17} className="text-neon" /> : <Circle size={17} className="text-edge" />}
                      <Icon size={16} className={le.lesson_type === "lab" ? "text-warn" : "text-cyber"} />
                      <span className="flex-1 text-sm">{le.title}</span>
                      <span className="text-xs font-mono text-muted">{le.duration} {t("common.minutes")}</span>
                    </Link>
                  </li>
                );
              })}
              {m.quiz && (
                <li>
                  <Link to={`/quizzes/${m.quiz.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-white/5 text-violet">
                    <ClipboardCheck size={17} />
                    <span className="flex-1 text-sm">{t("courses.quiz")}: {m.quiz.title}</span>
                    <span className="text-xs font-mono">{m.quiz.questions} Q</span>
                  </Link>
                </li>
              )}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
