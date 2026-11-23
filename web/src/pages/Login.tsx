import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, serverUrl, setServerUrl } from "../api/client";
import { Logo, ErrorBox } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { LANGS } from "../i18n";

const isDesktop = "__TAURI_INTERNALS__" in window;

export default function Login() {
  const { t, i18n } = useTranslation();
  const { login } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [f, setF] = useState({ login: "", username: "", email: "", password: "", full_name: "" });
  const [server, setServer] = useState(serverUrl() || (isDesktop ? "http://localhost:8000" : ""));
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      if (isDesktop || server) setServerUrl(server);
      if (mode === "register") {
        await api("/auth/register", {
          method: "POST",
          json: { username: f.username, email: f.email, password: f.password, full_name: f.full_name, preferred_language: i18n.language },
        });
        await login(f.username, f.password);
      } else {
        await login(f.login, f.password);
      }
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-40 font-mono text-[11px] leading-4 text-neon/20 select-none whitespace-pre overflow-hidden">
        {Array.from({ length: 60 }, (_, i) => `${(0x1f3a + i * 977).toString(16)}  SYN → 10.200.${i % 8}.${(i * 7) % 254}:${[22, 80, 443, 21, 3306, 445][i % 6]}  ${i % 5 ? "OPEN" : "FILTERED"}  `.repeat(4)).join("\n")}
      </div>
      <div className="relative w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <Logo size={56} />
          <h1 className="mt-4 font-mono text-3xl text-neon glow-text">CLPE</h1>
          <p className="text-muted text-sm mt-1 text-center">{t("app.tagline")}</p>
        </div>
        <form onSubmit={submit} className="panel p-6 space-y-4 shadow-neon">
          <div className="flex border-b border-edge -mx-6 px-6 -mt-2">
            {(["login", "register"] as const).map((m) => (
              <button type="button" key={m} onClick={() => setMode(m)} className={`tab ${mode === m ? "tab-active" : ""}`}>
                {t(`auth.${m}`)}
              </button>
            ))}
          </div>
          {mode === "login" ? (
            <div>
              <label className="label">{t("auth.loginField")}</label>
              <input className="input" value={f.login} onChange={set("login")} autoFocus required />
            </div>
          ) : (
            <>
              <div>
                <label className="label">{t("auth.username")}</label>
                <input className="input" value={f.username} onChange={set("username")} required minLength={3} />
              </div>
              <div>
                <label className="label">{t("auth.email")}</label>
                <input className="input" type="email" value={f.email} onChange={set("email")} required />
              </div>
              <div>
                <label className="label">{t("auth.fullName")}</label>
                <input className="input" value={f.full_name} onChange={set("full_name")} />
              </div>
            </>
          )}
          <div>
            <label className="label">{t("auth.password")}</label>
            <input className="input" type="password" value={f.password} onChange={set("password")} required minLength={mode === "register" ? 8 : 1} />
          </div>
          {isDesktop && (
            <div>
              <label className="label">{t("auth.server")}</label>
              <input className="input" value={server} onChange={(e) => setServer(e.target.value)} placeholder="https://clpe.university.uz" />
            </div>
          )}
          <ErrorBox msg={err} />
          <button className="btn-primary w-full py-2.5" disabled={busy}>
            {busy ? "…" : t(`auth.${mode}`)}
          </button>
          <div className="flex justify-center gap-3 pt-1">
            {LANGS.map((l) => (
              <button type="button" key={l.code} onClick={() => i18n.changeLanguage(l.code)}
                className={`text-xs font-mono ${i18n.language === l.code ? "text-neon" : "text-muted hover:text-slate-300"}`}>
                {l.code.toUpperCase()}
              </button>
            ))}
          </div>
        </form>
      </div>
    </div>
  );
}
