import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BookOpen, Flag, FlaskConical, LayoutDashboard, LogOut, MonitorDot, ShieldCheck, Trophy } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { LANGS } from "../i18n";
import { Logo, Progress } from "./ui";

export default function Layout() {
  const { t, i18n } = useTranslation();
  const { user, logout, can } = useAuth();
  const nav = [
    { to: "/", icon: LayoutDashboard, label: t("nav.dashboard"), end: true },
    { to: "/courses", icon: BookOpen, label: t("nav.courses") },
    { to: "/labs", icon: FlaskConical, label: t("nav.labs") },
    { to: "/ctf", icon: Flag, label: t("nav.ctf") },
    { to: "/leaderboard", icon: Trophy, label: t("nav.leaderboard") },
    ...(can("labs:monitor") ? [{ to: "/monitor", icon: MonitorDot, label: t("nav.monitor") }] : []),
    ...(can("content:write") || can("labs:author") || can("users:manage")
      ? [{ to: "/admin", icon: ShieldCheck, label: t("nav.admin") }]
      : []),
  ];
  const xpInLevel = (user?.xp ?? 0) % 500;

  return (
    <div className="flex min-h-full">
      <aside className="w-60 shrink-0 border-r border-edge bg-panel/70 backdrop-blur flex flex-col sticky top-0 h-screen">
        <div className="px-5 py-5 flex items-center gap-3 border-b border-edge">
          <Logo />
          <div>
            <div className="font-mono text-lg text-neon glow-text leading-none">CLPE</div>
            <div className="text-[10px] text-muted font-mono uppercase tracking-widest mt-1">cyber range</div>
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {nav.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  isActive ? "bg-neon/10 text-neon shadow-neon" : "text-slate-400 hover:text-slate-100 hover:bg-white/5"
                }`
              }
            >
              <Icon size={17} /> {label}
            </NavLink>
          ))}
        </nav>
        {user && (
          <div className="p-4 border-t border-edge space-y-3">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-cyber/10 border border-cyber/40 text-cyber flex items-center justify-center font-mono">
                {user.username[0]?.toUpperCase()}
              </div>
              <div className="min-w-0">
                <div className="text-sm text-slate-100 truncate">{user.full_name || user.username}</div>
                <div className="text-[11px] font-mono text-muted">
                  LVL {user.level} · {user.xp} XP
                </div>
              </div>
            </div>
            <Progress value={(xpInLevel / 500) * 100} color="cyber" />
            <div className="flex items-center gap-2">
              <select
                aria-label="language"
                value={i18n.language}
                onChange={(e) => i18n.changeLanguage(e.target.value)}
                className="input py-1 text-xs"
              >
                {LANGS.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
              <button className="btn-ghost px-2 py-1" onClick={logout} title={t("nav.logout")}>
                <LogOut size={15} />
              </button>
            </div>
          </div>
        )}
      </aside>
      <main className="flex-1 min-w-0 p-6 lg:p-8">
        <Outlet />
      </main>
    </div>
  );
}
