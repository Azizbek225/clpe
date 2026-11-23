import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { CheckCircle2, FilePlus2, Save, ShieldCheck } from "lucide-react";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { Difficulty, toast } from "../../components/ui";

const SKELETON = `id: my-new-lab-001
version: 1
title:
  uz: Yangi laboratoriya
  ru: Новая лаборатория
  en: New lab
description:
  uz: Qisqa tavsif
category: web-security
course: web-application-security
lab_type: offensive        # offensive | defensive | forensics | malware
difficulty: beginner       # beginner | intermediate | advanced
duration_minutes: 60
objectives:
  - {uz: "Birinchi maqsad"}
instructions:
  uz: |
    ## Vazifa
    Markdown formatida yo'riqnoma.
machines:
  - {name: attacker, template: kali-linux, role: attacker}
  - {name: target, template: dvwa, role: target, hidden: true}
networks:
  - {name: lab, type: isolated, internet: false}
topology: {reveal: discovered}   # discovered | full
resources: {cpu: 2, ram: 2048, max_machines: 4}
tasks:
  - id: ports
    title: {uz: "Ochiq portlarni toping"}
    points: 30
    validation: {type: port_discovery, machine: target}
  - id: flag
    title: {uz: "Flagni toping"}
    points: 70
    validation: {type: flag, flag: "CLPE{change_me}"}
scoring: {maximum: 100, passing: 60, xp: 150}
cleanup: {snapshot_restore: true, auto_shutdown: true, destroy_on_stop: true}
`;

export default function LabEditor() {
  const { t } = useTranslation();
  const { data: labs, reload } = useApi<any[]>("/admin/labs");
  const { data: engine } = useApi<any>("/admin/lab-engine");
  const [slug, setSlug] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [result, setResult] = useState<{ valid: boolean; errors: string[] } | null>(null);

  useEffect(() => {
    if (slug) api<string>(`/admin/labs/${slug}/manifest`, { raw: true }).then((x) => { setText(x); setResult(null); });
  }, [slug]);

  const validate = async () => setResult(await api("/admin/labs/validate", { method: "POST", json: { yaml: text } }));
  const save = async () => {
    try {
      const r = await api("/admin/labs", { method: "POST", json: { yaml: text } });
      toast(`${r.slug} v${r.version} — ${t("common.saved")}`);
      setResult({ valid: true, errors: [] });
      setSlug(r.slug);
      reload();
    } catch (e: any) {
      setResult({ valid: false, errors: e.message.split("; ") });
    }
  };
  const setStatus = async (s: string, status: string) => {
    await api(`/admin/labs/${s}/status?status=${status}`, { method: "POST" });
    reload();
  };

  return (
    <div className="grid lg:grid-cols-4 gap-5">
      <aside className="panel p-3 h-fit space-y-1">
        <button className="btn-primary w-full mb-2" onClick={() => { setSlug(null); setText(SKELETON); setResult(null); }}>
          <FilePlus2 size={15} /> {t("admin.newLab")}
        </button>
        {labs?.map((l) => (
          <button key={l.slug} onClick={() => setSlug(l.slug)} className={`w-full text-left rounded-lg px-3 py-2 text-sm ${slug === l.slug ? "bg-neon/10 text-neon" : "hover:bg-white/5"}`}>
            <div className="font-mono text-xs">{l.slug}</div>
            <div className="flex items-center gap-2 mt-1 text-[11px] text-muted">
              <Difficulty level={l.difficulty} /> v{l.version} · {l.machines} VM · {l.tasks} T
              <span className={l.status === "published" ? "text-neon" : "text-warn"}>{l.status}</span>
            </div>
          </button>
        ))}
      </aside>
      <div className="lg:col-span-3 space-y-4">
        <div className="panel p-1">
          <textarea spellCheck={false} className="w-full h-[560px] bg-void text-[13px] font-mono text-slate-200 p-4 rounded-lg focus:outline-none resize-y"
            value={text} onChange={(e) => setText(e.target.value)} placeholder="# YAML manifest" />
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <button className="btn-cyber" onClick={validate} disabled={!text}><ShieldCheck size={15} /> {t("admin.validate")}</button>
          <button className="btn-primary" onClick={save} disabled={!text}><Save size={15} /> {t("common.save")}</button>
          {slug && (
            <>
              <button className="btn-ghost" onClick={() => setStatus(slug, "published")}>publish</button>
              <button className="btn-ghost" onClick={() => setStatus(slug, "draft")}>draft</button>
            </>
          )}
        </div>
        {result && (
          <div className={`panel p-4 font-mono text-sm ${result.valid ? "border-neon/50 text-neon" : "border-threat/50 text-threat"}`}>
            {result.valid ? <span className="flex items-center gap-2"><CheckCircle2 size={16} /> {t("admin.valid")}</span>
              : <ul className="space-y-1">{result.errors.map((e) => <li key={e}>✖ {e}</li>)}</ul>}
          </div>
        )}
        {engine && (
          <div className="panel p-4 text-xs font-mono text-muted space-y-2">
            <div><span className="text-cyber">templates:</span> {engine.templates.map((x: any) => x.slug).join(", ")}</div>
            <div><span className="text-cyber">validation types:</span> {engine.validator_types.join(", ")}</div>
            <div><span className="text-cyber">network types:</span> isolated, internal (bridged — forbidden)</div>
          </div>
        )}
      </div>
    </div>
  );
}
