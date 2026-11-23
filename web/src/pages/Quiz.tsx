import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { ErrorBox, PageHeader, Spinner } from "../components/ui";

type Q = { id: string; text: string; type: string; options: { id: string; text: string }[] };

export default function Quiz() {
  const { id } = useParams();
  const { t } = useTranslation();
  const [quiz, setQuiz] = useState<{ attempt_id: string; title: string; passing_score: number; questions: Q[] } | null>(null);
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  const start = () => {
    setResult(null);
    setAnswers({});
    api(`/quizzes/${id}/start`, { method: "POST" }).then(setQuiz).catch((e) => setErr(e.message));
  };
  useEffect(start, [id]);

  if (err) return <ErrorBox msg={err} />;
  if (!quiz) return <Spinner />;

  const toggle = (q: Q, opt: string) =>
    setAnswers((a) => ({
      ...a,
      [q.id]: q.type === "multiple" ? (a[q.id]?.includes(opt) ? a[q.id].filter((x) => x !== opt) : [...(a[q.id] ?? []), opt]) : [opt],
    }));

  const submit = async () => setResult(await api(`/quizzes/${id}/submit`, { method: "POST", json: { attempt_id: quiz.attempt_id, answers } }));
  const review = (qid: string) => result?.review.find((r: any) => r.question_id === qid);

  return (
    <div className="max-w-3xl">
      <PageHeader title={quiz.title} subtitle={`≥ ${quiz.passing_score}%`} />
      {result && (
        <div className={`panel p-5 mb-6 ${result.passed ? "border-neon/60 shadow-neon" : "border-threat/60 shadow-threat"}`}>
          <div className={`font-mono text-3xl ${result.passed ? "text-neon" : "text-threat"}`}>{result.score}%</div>
          <div className="mt-1">{result.passed ? t("quiz.passed") : t("quiz.failed")} ({result.correct}/{result.total})</div>
          {result.certificate && <div className="mt-2 text-violet font-mono">🏅 {t("quiz.certificate")}: {result.certificate.number}</div>}
          <button className="btn-ghost mt-3" onClick={start}>{t("quiz.retry")}</button>
        </div>
      )}
      <div className="space-y-4">
        {quiz.questions.map((q, i) => {
          const r = review(q.id);
          return (
            <div key={q.id} className={`panel p-5 ${r ? (r.correct ? "border-neon/50" : "border-threat/50") : ""}`}>
              <div className="text-sm mb-3"><span className="font-mono text-cyber mr-2">{String(i + 1).padStart(2, "0")}</span>{q.text}</div>
              <div className="space-y-2">
                {q.options.map((o) => {
                  const chosen = answers[q.id]?.includes(o.id);
                  const correct = r?.correct_options.includes(o.id);
                  return (
                    <button key={o.id} disabled={!!result} onClick={() => toggle(q, o.id)}
                      className={`w-full text-left px-3 py-2 rounded-lg border text-sm transition ${
                        r && correct ? "border-neon/60 bg-neon/10" : chosen ? "border-cyber/60 bg-cyber/10" : "border-edge hover:border-slate-500"}`}>
                      <span className="font-mono mr-2 text-muted">{q.type === "multiple" ? (chosen ? "[x]" : "[ ]") : chosen ? "(•)" : "( )"}</span>
                      {o.text}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      {!result && <button className="btn-primary mt-6" onClick={submit}>{t("quiz.submit")}</button>}
    </div>
  );
}
