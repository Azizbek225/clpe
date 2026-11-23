import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Loader2 } from "lucide-react";

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <path d="M32 4 56 13v17c0 15-10 26-24 30C18 56 8 45 8 30V13z" fill="rgba(0,255,156,.08)" stroke="#00ff9c" strokeWidth="3.5" />
      <path d="M22 31l7 7 13-14" fill="none" stroke="#22d3ee" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const DIFF: Record<string, string> = {
  beginner: "text-neon border-neon/40 bg-neon/5",
  intermediate: "text-warn border-warn/40 bg-warn/5",
  advanced: "text-threat border-threat/40 bg-threat/5",
  easy: "text-neon border-neon/40 bg-neon/5",
  medium: "text-warn border-warn/40 bg-warn/5",
  hard: "text-threat border-threat/40 bg-threat/5",
};

export function Difficulty({ level }: { level: string }) {
  const { t } = useTranslation();
  const label = t(`level.${level}`, { defaultValue: level });
  return <span className={`chip ${DIFF[level] ?? "text-muted border-edge"}`}>{label}</span>;
}

const STATUS: Record<string, string> = {
  RUNNING: "text-neon border-neon/40",
  STARTING: "text-cyber border-cyber/40",
  PREPARING: "text-cyber border-cyber/40",
  CREATED: "text-cyber border-cyber/40",
  RESETTING: "text-violet border-violet/40",
  QUEUED: "text-warn border-warn/40",
  STOPPING: "text-warn border-warn/40",
  STOPPED: "text-muted border-edge",
  ERROR: "text-threat border-threat/40",
  PAUSED: "text-warn border-warn/40",
};

export function StatusPill({ status }: { status: string }) {
  const live = ["RUNNING", "STARTING", "PREPARING", "RESETTING", "CREATED"].includes(status);
  return (
    <span className={`chip ${STATUS[status] ?? "text-muted border-edge"}`}>
      <span className={`h-1.5 w-1.5 rounded-full bg-current ${live ? "animate-pulseDot" : ""}`} />
      {status}
    </span>
  );
}

export function Progress({ value, color = "neon" }: { value: number; color?: "neon" | "cyber" | "warn" | "threat" }) {
  const bg = { neon: "bg-neon", cyber: "bg-cyber", warn: "bg-warn", threat: "bg-threat" }[color];
  return (
    <div className="h-1.5 w-full rounded-full bg-edge/70 overflow-hidden">
      <div className={`h-full ${bg} shadow-[0_0_10px_currentColor] transition-all`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
    </div>
  );
}

export function Stat({ label, value, icon, accent = "text-neon" }: { label: string; value: ReactNode; icon?: ReactNode; accent?: string }) {
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between text-muted text-xs font-mono uppercase tracking-wider">
        {label}
        <span className={accent}>{icon}</span>
      </div>
      <div className={`mt-2 text-2xl font-mono ${accent}`}>{value}</div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2 text-muted font-mono text-sm py-8 justify-center">
      <Loader2 className="animate-spin text-neon" size={18} /> {label ?? t("common.loading")}
    </div>
  );
}

export function ErrorBox({ msg }: { msg: string | null }) {
  if (!msg) return null;
  return <div className="panel border-threat/50 text-threat px-4 py-3 text-sm font-mono">⚠ {msg}</div>;
}

export function Markdown({ text }: { text: string }) {
  return (
    <div className="prose-cyber">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions, icon }: { title: string; subtitle?: string; actions?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div>
        <h1 className="font-mono text-2xl text-slate-100 flex items-center gap-3">
          {icon && <span className="text-neon">{icon}</span>}
          <span>{title}</span>
        </h1>
        {subtitle && <p className="text-muted mt-1 text-sm max-w-3xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

/** Kichik toast — global hodisa orqali */
export function toast(msg: string, kind: "ok" | "err" = "ok") {
  window.dispatchEvent(new CustomEvent("clpe:toast", { detail: { msg, kind } }));
}

export function Toaster() {
  const [items, setItems] = useState<{ id: number; msg: string; kind: string }[]>([]);
  useEffect(() => {
    const h = (e: Event) => {
      const d = (e as CustomEvent).detail;
      const id = Date.now() + Math.random();
      setItems((x) => [...x, { id, ...d }]);
      setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 3500);
    };
    window.addEventListener("clpe:toast", h);
    return () => window.removeEventListener("clpe:toast", h);
  }, []);
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {items.map((i) => (
        <div key={i.id} className={`panel px-4 py-3 text-sm font-mono ${i.kind === "err" ? "border-threat/60 text-threat shadow-threat" : "border-neon/60 text-neon shadow-neon"}`}>
          {i.kind === "err" ? "✖ " : "✔ "}
          {i.msg}
        </div>
      ))}
    </div>
  );
}

export function Empty({ children }: { children?: ReactNode }) {
  const { t } = useTranslation();
  return <div className="text-muted text-sm font-mono py-6 text-center">{children ?? t("common.none")}</div>;
}
