import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Activity, Camera, CheckCircle2, Cpu, Lightbulb, Play, Radar, RotateCcw, ShieldCheck, Square, TerminalSquare, Upload, XCircle } from "lucide-react";
import { api, getAccessToken, wsUrl } from "../api/client";
import type { LabDetail, LabTask, Machine, Topology } from "../api/types";
import { Difficulty, ErrorBox, Markdown, Progress, Spinner, StatusPill, toast } from "../components/ui";
import TopologyGraph from "../components/TopologyGraph";
import Terminal from "../components/Terminal";

type Tab = "topology" | "terminal" | "machines" | "events";

function useCountdown(expires: string | null | undefined) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const i = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(i);
  }, []);
  if (!expires) return null;
  const ms = new Date(expires).getTime() - now;
  if (ms <= 0) return "00:00";
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function LabWorkspace() {
  const { slug } = useParams();
  const { t, i18n } = useTranslation();
  const [lab, setLab] = useState<LabDetail | null>(null);
  const [topo, setTopo] = useState<Topology | null>(null);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [tab, setTab] = useState<Tab>("topology");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await api<LabDetail>(`/labs/${slug}?lang=${i18n.language}`);
      setLab(d);
      if (d.instance && d.instance.status !== "STOPPED") {
        const [tp, ms, ev] = await Promise.all([
          api<Topology>(`/labs/${slug}/topology`),
          api<Machine[]>(`/labs/${slug}/machines`),
          api<any[]>(`/labs/${slug}/events`),
        ]);
        setTopo(tp);
        setMachines(ms);
        setEvents(ev);
      }
    } catch (e: any) {
      setErr(e.message);
    }
  }, [slug, i18n.language]);

  useEffect(() => {
    load();
  }, [load]);

  const inst = lab?.instance;
  const status = inst?.status;
  const live = !!inst && !["STOPPED", "ERROR"].includes(inst.status);

  // Real vaqt: WebSocket orqali status/metrika/hodisalar
  useEffect(() => {
    if (!live) return;
    const ws = new WebSocket(wsUrl(`/ws/labs/${inst!.id}?token=${encodeURIComponent(getAccessToken() ?? "")}`));
    let last = inst!.status;
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.events?.length) setEvents((x) => [...x, ...m.events].slice(-300));
      setMachines((ms) => ms.map((x) => (m.metrics?.[x.name] ? { ...x, status: m.machines[x.name], metrics: { cpu_percent: m.metrics[x.name].cpu, ram_used_mb: m.metrics[x.name].ram, ram_limit_mb: m.metrics[x.name].ram_limit } } : x)));
      if (m.status !== last) {
        last = m.status;
        load();
      }
    };
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inst?.id, live]);

  const act = async (path: string, body?: unknown, msg?: string) => {
    setBusy(true);
    try {
      await api(`/labs/${slug}/${path}`, { method: "POST", json: body ?? {} });
      if (msg) toast(msg);
      await load();
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setBusy(false);
    }
  };

  const timeLeft = useCountdown(status === "RUNNING" ? inst?.expires_at : null);
  if (!lab) return err ? <ErrorBox msg={err} /> : <Spinner />;
  const solved = Object.values(inst?.tasks ?? {}).filter((x) => x.passed).length;

  return (
    <div>
      <Link to="/labs" className="text-sm text-muted hover:text-neon font-mono">← {t("nav.labs")}</Link>
      <div className="panel p-5 mt-3 mb-5 flex flex-wrap items-center gap-4 justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-muted">
            <span>{lab.id}</span> · <span>v{lab.version}</span> · <Difficulty level={lab.difficulty} />
            {status && <StatusPill status={status} />}
          </div>
          <h1 className="font-mono text-2xl text-slate-100 mt-1">{lab.title}</h1>
          <div className="text-xs text-muted mt-1 flex items-center gap-1"><ShieldCheck size={13} className="text-neon" /> {t("labs.isolation")}</div>
        </div>
        <div className="flex items-center gap-6">
          {inst && (
            <div className="text-right font-mono">
              <div className="text-xs text-muted">{t("labs.score")}</div>
              <div className="text-2xl text-warn">{inst.score}<span className="text-muted text-sm">/{lab.scoring.maximum}</span></div>
            </div>
          )}
          {timeLeft && (
            <div className="text-right font-mono">
              <div className="text-xs text-muted">{t("labs.timeLeft")}</div>
              <div className="text-2xl text-cyber">{timeLeft}</div>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {!live ? (
              <button className="btn-primary" disabled={busy} onClick={() => act("start", undefined, t("labs.start"))}>
                <Play size={15} /> {t("labs.start")}
              </button>
            ) : (
              <>
                <button className="btn-ghost" disabled={busy || status !== "RUNNING"} onClick={() => act("snapshot", { name: "checkpoint" }, "Snapshot ✓")} title={t("labs.snapshot")}>
                  <Camera size={15} />
                </button>
                <button className="btn-ghost" disabled={busy || status !== "RUNNING"} onClick={() => act("restore", { name: "checkpoint" }, t("labs.restore"))} title={t("labs.restore")}>
                  <RotateCcw size={15} /> cp
                </button>
                <button className="btn-cyber" disabled={busy || status !== "RUNNING"} onClick={() => act("reset", undefined, t("labs.reset"))}>
                  <RotateCcw size={15} /> {t("labs.reset")}
                </button>
                <button className="btn-danger" disabled={busy} onClick={() => act("stop", undefined, t("labs.stop"))}>
                  <Square size={15} /> {t("labs.stop")}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
      {inst?.status === "ERROR" && <div className="mb-4"><ErrorBox msg={inst.error} /></div>}

      <div className="grid xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2 space-y-5">
          {!live ? (
            <Briefing lab={lab} />
          ) : (
            <div className="panel">
              <div className="flex border-b border-edge px-3">
                {([
                  ["topology", Radar, t("labs.topology")],
                  ["terminal", TerminalSquare, t("labs.terminal")],
                  ["machines", Cpu, t("labs.machinesTab")],
                  ["events", Activity, t("labs.events")],
                ] as const).map(([k, Icon, label]) => (
                  <button key={k} className={`tab flex items-center gap-2 ${tab === k ? "tab-active" : ""}`} onClick={() => setTab(k)}>
                    <Icon size={15} /> {label}
                  </button>
                ))}
              </div>
              <div className="p-4">
                {tab === "topology" && <TopologyPanel slug={slug!} lab={lab} topo={topo} setTopo={setTopo} />}
                {tab === "terminal" && <TerminalPanel machines={machines} />}
                {tab === "machines" && <MachinesPanel machines={machines} />}
                {tab === "events" && <EventsPanel events={events} />}
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-5">
          <section className="panel p-5">
            <h2 className="font-mono text-cyber mb-3">{t("labs.instructions")}</h2>
            <div className="max-h-[360px] overflow-y-auto pr-1 text-sm">
              <Markdown text={lab.instructions} />
            </div>
          </section>
          <section className="panel p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-mono text-cyber">{t("labs.taskList")}</h2>
              <span className="font-mono text-xs text-muted">{solved}/{lab.tasks.length}</span>
            </div>
            <Progress value={(solved / Math.max(1, lab.tasks.length)) * 100} />
            <div className="space-y-3 mt-4">
              {lab.tasks.map((task, i) => (
                <TaskCard key={task.id} idx={i} task={task} state={inst?.tasks[task.id]} disabled={status !== "RUNNING"}
                  onSubmit={async (body) => {
                    const r = await api(`/labs/${slug}/submit`, { method: "POST", json: { task_id: task.id, ...body } });
                    toast(r.feedback, r.passed || r.pending ? "ok" : "err");
                    load();
                  }} />
              ))}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

function Briefing({ lab }: { lab: LabDetail }) {
  const { t } = useTranslation();
  return (
    <div className="panel p-6 space-y-5">
      <p className="text-slate-300">{lab.description}</p>
      <div className="text-sm text-muted">{t("labs.notStarted")}</div>
      {lab.objectives.length > 0 && (
        <div>
          <h3 className="label">{t("courses.objectives")}</h3>
          <ul className="text-sm space-y-1">{lab.objectives.map((o) => <li key={o}><span className="text-neon">▸</span> {o}</li>)}</ul>
        </div>
      )}
      <div className="grid sm:grid-cols-2 gap-3">
        {lab.machines.map((m) => (
          <div key={m.name} className={`rounded-lg border px-4 py-3 font-mono text-sm ${m.role === "attacker" ? "border-neon/40 text-neon" : "border-threat/40 text-threat"}`}>
            <div>{m.name}</div>
            <div className="text-xs text-muted">{m.template} · {m.role}</div>
          </div>
        ))}
        {lab.networks.map((n) => (
          <div key={n.name} className="rounded-lg border border-cyber/40 px-4 py-3 font-mono text-sm text-cyber">
            ⬢ {n.name}<div className="text-xs text-muted">{n.type} · internet: {n.internet ? "on" : "off"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TopologyPanel({ slug, lab, topo, setTopo }: { slug: string; lab: LabDetail; topo: Topology | null; setTopo: (t: Topology) => void }) {
  const { t } = useTranslation();
  const attackerNet = lab.instance?.machines.find((m) => m.role === "attacker");
  const defaultTarget = useMemo(() => {
    const net = attackerNet ? Object.keys(attackerNet.ips)[0] : lab.instance?.networks[0]?.name;
    return lab.instance?.networks.find((n) => n.name === net)?.cidr ?? "";
  }, [lab, attackerNet]);
  const [target, setTarget] = useState(defaultTarget);
  const [profile, setProfile] = useState("services");
  const [scanning, setScanning] = useState(false);
  const running = lab.instance?.status === "RUNNING";
  const [xml, setXml] = useState("");
  const [showImport, setShowImport] = useState(false);

  const scan = async () => {
    setScanning(true);
    try {
      const r = await api(`/labs/${slug}/scan`, { method: "POST", json: { target, profile } });
      setTopo(r.topology);
      toast(`${r.hosts.length} host`);
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setScanning(false);
    }
  };
  const importXml = async () => {
    try {
      const r = await api(`/labs/${slug}/scan/import`, { method: "POST", json: { xml } });
      setTopo(r.topology);
      setXml("");
      setShowImport(false);
      toast(`${r.hosts.length} host`);
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[180px]">
          <label className="label">{t("labs.scanTarget")}</label>
          <input className="input font-mono" value={target} onChange={(e) => setTarget(e.target.value)} />
        </div>
        <div>
          <label className="label">nmap</label>
          <select className="input font-mono" value={profile} onChange={(e) => setProfile(e.target.value)}>
            {lab.scan_profiles.map((p) => <option key={p}>{p}</option>)}
          </select>
        </div>
        <button className="btn-primary" disabled={scanning || !target || !running} onClick={scan} title={running ? undefined : t("labs.waitRunning")}>
          <Radar size={15} className={scanning ? "animate-spin" : ""} /> {t("labs.scan")}
        </button>
        <button className="btn-ghost" onClick={() => setShowImport((x) => !x)}><Upload size={15} /> XML</button>
      </div>
      {!running && <div className="text-xs text-warn font-mono">{t("labs.waitRunning")}</div>}
      {showImport && (
        <div className="space-y-2">
          <div className="text-xs text-muted font-mono">{t("labs.importHint")}</div>
          <textarea className="input font-mono text-xs h-32" value={xml} onChange={(e) => setXml(e.target.value)} placeholder="<?xml version=... <nmaprun ...>" />
          <button className="btn-cyber" disabled={!xml} onClick={importXml}>{t("labs.importXml")}</button>
        </div>
      )}
      <TopologyGraph data={topo} scanning={scanning} />
    </div>
  );
}

function TerminalPanel({ machines }: { machines: Machine[] }) {
  const { t } = useTranslation();
  const consoles = machines.filter((m) => m.console);
  const [sel, setSel] = useState(consoles[0]?.id);
  if (!consoles.length) return <div className="text-sm text-muted font-mono py-10 text-center">{t("labs.noConsole")}</div>;
  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {consoles.map((m) => (
          <button key={m.id} className={`chip px-3 py-1 ${sel === m.id ? "text-neon border-neon/50" : "text-muted border-edge"}`} onClick={() => setSel(m.id)}>
            {m.name}@{Object.values(m.ips)[0]}
          </button>
        ))}
      </div>
      {sel && <Terminal key={sel} machineId={sel} />}
    </div>
  );
}

function MachinesPanel({ machines }: { machines: Machine[] }) {
  return (
    <div className="grid md:grid-cols-2 gap-3">
      {machines.map((m) => (
        <div key={m.id} className="rounded-lg border border-edge p-4 font-mono text-sm">
          <div className="flex items-center justify-between">
            <span className={m.role === "attacker" ? "text-neon" : "text-threat"}>{m.name}</span>
            <StatusPill status={m.status} />
          </div>
          <div className="text-xs text-muted mt-1">{m.os}</div>
          <div className="text-xs text-cyber mt-1">{Object.entries(m.ips).map(([n, ip]) => `${n}: ${ip}`).join("  ") || "IP: ?"}</div>
          {m.metrics && (
            <div className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between text-muted"><span>CPU</span><span>{m.metrics.cpu_percent}%</span></div>
              <Progress value={m.metrics.cpu_percent} color="cyber" />
              <div className="flex justify-between text-muted"><span>RAM</span><span>{Math.round(m.metrics.ram_used_mb)} / {Math.round(m.metrics.ram_limit_mb)} MB</span></div>
              <Progress value={(m.metrics.ram_used_mb / Math.max(1, m.metrics.ram_limit_mb)) * 100} color="warn" />
            </div>
          )}
          <div className="text-[11px] text-muted mt-2">snapshots: {m.snapshots.join(", ") || "—"}</div>
        </div>
      ))}
    </div>
  );
}

function EventsPanel({ events }: { events: any[] }) {
  return (
    <div className="font-mono text-xs bg-void border border-edge rounded-lg p-3 h-[420px] overflow-y-auto space-y-1">
      {events.map((e, i) => (
        <div key={i} className="flex gap-3">
          <span className="text-muted shrink-0">{new Date(e.created_at).toLocaleTimeString()}</span>
          <span className={e.type === "warning" ? "text-warn" : e.type === "status" ? "text-cyber" : "text-neon"}>{e.type}</span>
          <span className="text-slate-400 break-all">{JSON.stringify(e.details)}</span>
        </div>
      ))}
    </div>
  );
}

function TaskCard({ idx, task, state, disabled, onSubmit }: {
  idx: number; task: LabTask; state?: { score: number; passed: boolean; feedback: string }; disabled: boolean;
  onSubmit: (body: Record<string, unknown>) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [val, setVal] = useState("");
  const [hint, setHint] = useState(false);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      const body =
        task.input === "ports" ? { ports: val.split(/[\s,]+/).filter(Boolean).map(Number) }
        : task.input === "hosts" ? { hosts: val.split(/[\s,]+/).filter(Boolean) }
        : task.input === "text" || task.validation_type === "manual" ? { value: val } : {};
      await onSubmit(body);
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setBusy(false);
    }
  };
  const needsInput = task.input !== "none" || task.validation_type === "manual";
  return (
    <div className={`rounded-lg border p-3 ${state?.passed ? "border-neon/50 bg-neon/5" : "border-edge"}`}>
      <div className="flex items-start gap-2">
        {state?.passed ? <CheckCircle2 size={16} className="text-neon mt-0.5" /> : state ? <XCircle size={16} className="text-threat mt-0.5" /> : <span className="font-mono text-xs text-muted mt-0.5">{String(idx + 1).padStart(2, "0")}</span>}
        <div className="flex-1">
          <div className="text-sm text-slate-100">{task.title}</div>
          {task.description && <div className="text-xs text-muted mt-0.5">{task.description}</div>}
        </div>
        <span className="font-mono text-xs text-warn">{state?.score ?? 0}/{task.points}</span>
      </div>
      {!state?.passed && (
        <div className="mt-2 flex gap-2">
          {needsInput && (
            task.validation_type === "manual"
              ? <textarea className="input text-xs h-20" value={val} onChange={(e) => setVal(e.target.value)} disabled={disabled} />
              : <input className="input font-mono text-xs" value={val} onChange={(e) => setVal(e.target.value)} disabled={disabled}
                  placeholder={task.input === "ports" ? t("labs.ports") : task.input === "hosts" ? t("labs.hosts") : t("labs.answer")}
                  onKeyDown={(e) => e.key === "Enter" && submit()} />
          )}
          <button className="btn-primary px-3 shrink-0" disabled={disabled || busy || (needsInput && !val)} onClick={submit}>{t("labs.submit")}</button>
        </div>
      )}
      {state?.feedback && <div className={`text-[11px] font-mono mt-2 ${state.passed ? "text-neon" : "text-muted"}`}>{state.feedback}</div>}
      {task.hint && (
        <button className="text-[11px] text-warn/80 mt-1 flex items-center gap-1" onClick={() => setHint(!hint)}>
          <Lightbulb size={12} /> {t("labs.hint")}{hint && `: ${task.hint}`}
        </button>
      )}
    </div>
  );
}
