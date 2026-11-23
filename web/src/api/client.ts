/* CLPE API mijozi: access token xotirada/localStorage, 401 bo'lsa refresh token bilan yangilanadi. */

const KEY = "clpe.auth";
const SERVER_KEY = "clpe.server";

export type Tokens = { access_token: string; refresh_token: string };

function safeGet(k: string): string | null {
  try {
    return localStorage.getItem(k);
  } catch {
    return null;
  }
}
function safeSet(k: string, v: string | null) {
  try {
    if (v === null) localStorage.removeItem(k);
    else localStorage.setItem(k, v);
  } catch {
    /* ignore */
  }
}

/** Web'da bo'sh (shu domen). Desktop (Tauri) ilovada foydalanuvchi server manzilini kiritadi. */
export function serverUrl(): string {
  return (safeGet(SERVER_KEY) || import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
}
export function setServerUrl(url: string) {
  safeSet(SERVER_KEY, url.trim() || null);
}
export function wsUrl(path: string): string {
  const base = serverUrl() || window.location.origin;
  return base.replace(/^http/, "ws") + path;
}

let tokens: Tokens | null = (() => {
  const raw = safeGet(KEY);
  return raw ? (JSON.parse(raw) as Tokens) : null;
})();

export function setTokens(t: Tokens | null) {
  tokens = t;
  safeSet(KEY, t ? JSON.stringify(t) : null);
}
export const getAccessToken = () => tokens?.access_token ?? null;
export const isLoggedIn = () => !!tokens;

export class ApiError extends Error {
  constructor(public status: number, message: string, public data?: unknown) {
    super(message);
  }
}

let refreshing: Promise<boolean> | null = null;
async function refresh(): Promise<boolean> {
  if (!tokens) return false;
  refreshing ??= (async () => {
    try {
      const r = await fetch(`${serverUrl()}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: tokens!.refresh_token }),
      });
      if (!r.ok) {
        setTokens(null);
        return false;
      }
      setTokens(await r.json());
      return true;
    } finally {
      setTimeout(() => (refreshing = null), 0);
    }
  })();
  return refreshing;
}

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown; raw?: boolean } = {}): Promise<T> {
  const { json, raw, ...init } = opts;
  const doFetch = () => {
    const headers = new Headers(init.headers);
    if (json !== undefined) headers.set("Content-Type", "application/json");
    if (tokens) headers.set("Authorization", `Bearer ${tokens.access_token}`);
    return fetch(`${serverUrl()}/api/v1${path}`, { ...init, headers, body: json !== undefined ? JSON.stringify(json) : init.body });
  };
  let res = await doFetch();
  if (res.status === 401 && tokens && (await refresh())) res = await doFetch();
  if (res.status === 401) {
    setTokens(null);
    window.dispatchEvent(new Event("clpe:logout"));
  }
  if (!res.ok) {
    let data: any = null;
    try {
      data = await res.json();
    } catch {
      /* not json */
    }
    const detail = data?.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg).join("; ")
          : detail?.errors?.join("; ") ?? res.statusText;
    throw new ApiError(res.status, msg, data);
  }
  if (res.status === 204) return undefined as T;
  if (raw) return (await res.text()) as T;
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("json") ? res.json() : res.text()) as Promise<T>;
}
