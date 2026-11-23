import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Flag } from "lucide-react";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import { Difficulty, PageHeader, Spinner, toast } from "../components/ui";

type Ch = { id: string; title: string; description: string; category: string; difficulty: string; points: number; solved: boolean; solves: number; lab_slug: string | null };

export default function Ctf() {
  const { t } = useTranslation();
  const { data, loading, reload } = useApi<Ch[]>("/ctf/challenges");
  const { data: board, reload: reloadBoard } = useApi<any[]>("/ctf/leaderboard");
  const [open, setOpen] = useState<Ch | null>(null);
  const [flag, setFlag] = useState("");
  if (loading) return <Spinner />;
  const byCat = (data ?? []).reduce<Record<string, Ch[]>>((a, c) => ((a[c.category] ??= []).push(c), a), {});

  const submit = async () => {
    const r = await api(`/ctf/challenges/${open!.id}/submit`, { method: "POST", json: { flag } });
    toast(r.correct ? `${t("ctf.correct")} +${r.points}` : t("ctf.wrong"), r.correct ? "ok" : "err");
    if (r.correct) {
      setOpen(null);
      setFlag("");
      reload();
      reloadBoard();
    }
  };

  return (
    <div>
      <PageHeader title={t("ctf.title")} icon={<Flag />} subtitle="CLPE Warm-up CTF · flag format: CLPE{...}" />
      <div className="grid xl:grid-cols-4 gap-6">
        <div className="xl:col-span-3 space-y-6">
          {Object.entries(byCat).map(([cat, list]) => (
            <section key={cat}>
              <h2 className="font-mono text-cyber uppercase tracking-widest text-sm mb-3">// {cat}</h2>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {list.map((c) => (
                  <button key={c.id} onClick={() => setOpen(c)} className={`panel panel-hover p-4 text-left ${c.solved ? "border-neon/50 bg-neon/5" : ""}`}>
                    <div className="flex justify-between items-center">
                      <Difficulty level={c.difficulty} />
                      {c.solved && <CheckCircle2 size={16} className="text-neon" />}
                    </div>
                    <div className="mt-2 text-slate-100">{c.title}</div>
                    <div className="mt-2 flex justify-between font-mono text-xs">
                      <span className="text-warn">{c.points} {t("common.points")}</span>
                      <span className="text-muted">{c.solves} {t("ctf.solves")}</span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
        <aside className="panel p-4 h-fit">
          <h2 className="font-mono text-cyber mb-3">{t("board.ctf")}</h2>
          {(board ?? []).map((r) => (
            <div key={r.username} className="flex justify-between text-sm font-mono border-t border-edge py-2">
              <span><span className="text-muted mr-2">#{r.rank}</span>{r.username}</span>
              <span className="text-warn">{r.points}</span>
            </div>
          ))}
        </aside>
      </div>
      {open && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-40 p-4" onClick={() => setOpen(null)}>
          <div className="panel p-6 w-full max-w-lg shadow-neon" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between"><Difficulty level={open.difficulty} /><span className="font-mono text-warn">{open.points}</span></div>
            <h3 className="font-mono text-xl mt-3">{open.title}</h3>
            <p className="text-sm text-slate-300 mt-2 break-words font-mono">{open.description}</p>
            {open.lab_slug && <Link to={`/labs/${open.lab_slug}`} className="text-cyber text-sm underline mt-2 inline-block">→ {open.lab_slug}</Link>}
            {open.solved ? (
              <div className="text-neon mt-4 font-mono">✔ {t("ctf.solved")}</div>
            ) : (
              <div className="flex gap-2 mt-4">
                <input className="input font-mono" placeholder="CLPE{...}" value={flag} onChange={(e) => setFlag(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} autoFocus />
                <button className="btn-primary" onClick={submit} disabled={!flag}>{t("labs.submit")}</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
