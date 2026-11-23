import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import i18n from "../i18n";
import { api, isLoggedIn, setTokens } from "../api/client";
import type { User } from "../api/types";

type Ctx = {
  user: User | null;
  loading: boolean;
  login: (login: string, password: string) => Promise<void>;
  logout: () => void;
  reload: () => Promise<void>;
  can: (perm: string) => boolean;
};

const AuthCtx = createContext<Ctx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(isLoggedIn());

  const reload = useCallback(async () => {
    if (!isLoggedIn()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api<User>("/auth/me"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
    const onOut = () => setUser(null);
    window.addEventListener("clpe:logout", onOut);
    return () => window.removeEventListener("clpe:logout", onOut);
  }, [reload]);

  const login = async (login: string, password: string) => {
    const t = await api("/auth/login", { method: "POST", json: { login, password } });
    setTokens(t);
    const me = await api<User>("/auth/me");
    setUser(me);
    if (me.preferred_language && !localStorage.getItem("clpe.lang")) i18n.changeLanguage(me.preferred_language);
  };

  const logout = () => {
    const raw = localStorage.getItem("clpe.auth");
    if (raw) api("/auth/logout", { method: "POST", json: { refresh_token: JSON.parse(raw).refresh_token } }).catch(() => {});
    setTokens(null);
    setUser(null);
  };

  const can = (perm: string) => !!user?.permissions.includes(perm);

  return <AuthCtx.Provider value={{ user, loading, login, logout, reload, can }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
