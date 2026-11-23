import { useMemo, useState } from "react";
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationNodeDatum } from "d3-force";
import { useTranslation } from "react-i18next";
import { Globe, Monitor, Network, Server, ShieldAlert, Skull } from "lucide-react";
import type { TopoNode, Topology } from "../api/types";

type N = TopoNode & SimulationNodeDatum;
const W = 900;
const H = 520;

function color(n: TopoNode) {
  if (n.type === "internet") return n.blocked ? "#ff3b5c" : "#ffb020";
  if (n.type === "network") return "#22d3ee";
  if (n.you || n.role === "attacker") return "#00ff9c";
  if (n.role === "unknown") return "#ffb020";
  return "#ff3b5c";
}

/** Tarmoq topologiyasi grafigi: skan natijalaridan avtomatik quriladi. */
export default function TopologyGraph({ data, scanning }: { data: Topology | null; scanning?: boolean }) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string | null>(null);

  const layout = useMemo(() => {
    if (!data) return null;
    const nodes: N[] = data.nodes.map((n) => ({ ...n }));
    const nets = nodes.filter((n) => n.type === "network");
    nodes.forEach((n) => {
      if (n.type === "internet") {
        n.fx = W / 2;
        n.fy = 70;
      }
    });
    nets.forEach((n, i) => {
      n.x = (W / (nets.length + 1)) * (i + 1);
      n.y = H / 2 - 20;
    });
    const links = data.edges.map((e) => ({ ...e }));
    const sim = forceSimulation(nodes)
      .force("link", forceLink<N, any>(links).id((d) => d.id).distance((l: any) => (l.target.type === "internet" ? 190 : 150)).strength(0.9))
      .force("charge", forceManyBody().strength(-900))
      .force("x", forceX(W / 2).strength(0.04))
      .force("y", forceY((d: any) => (d.type === "network" ? H / 2 - 20 : d.type === "internet" ? 70 : H / 2 + 80)).strength(0.08))
      .force("collide", forceCollide(52))
      .stop();
    for (let i = 0; i < 400; i++) sim.tick();
    nodes.forEach((n) => {
      n.x = Math.max(60, Math.min(W - 60, n.x ?? 0));
      n.y = Math.max(60, Math.min(H - 70, n.y ?? 0));
    });
    return { nodes, links: links as unknown as { source: N; target: N; blocked?: boolean }[] };
  }, [data]);

  if (!layout) return null;
  const sel = layout.nodes.find((n) => n.id === selected) ?? null;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto rounded-lg bg-void/80 border border-edge">
        <defs>
          <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M24 0H0V24" fill="none" stroke="#12202f" strokeWidth="1" />
          </pattern>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3.5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="scanline" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#00ff9c" stopOpacity="0" />
            <stop offset="1" stopColor="#00ff9c" stopOpacity=".18" />
          </linearGradient>
        </defs>
        <rect width={W} height={H} fill="url(#grid)" />
        {scanning && (
          <rect width={W} height={80} fill="url(#scanline)">
            <animate attributeName="y" from={-80} to={H} dur="1.6s" repeatCount="indefinite" />
          </rect>
        )}

        {layout.links.map((l, i) => {
          const blocked = l.blocked;
          const mx = ((l.source.x ?? 0) + (l.target.x ?? 0)) / 2;
          const my = ((l.source.y ?? 0) + (l.target.y ?? 0)) / 2;
          return (
            <g key={i}>
              <line
                x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y}
                stroke={blocked ? "#ff3b5c" : "#22d3ee"} strokeOpacity={blocked ? 0.55 : 0.6}
                strokeWidth={blocked ? 1.5 : 2} strokeDasharray={blocked ? "6 6" : undefined}
              >
                {!blocked && <animate attributeName="stroke-dashoffset" from="0" to="-20" dur="1s" repeatCount="indefinite" />}
              </line>
              {!blocked && <line x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y} stroke="#22d3ee" strokeOpacity=".35" strokeWidth="2" strokeDasharray="2 18">
                <animate attributeName="stroke-dashoffset" from="0" to="-40" dur="1.4s" repeatCount="indefinite" />
              </line>}
              {blocked && (
                <g transform={`translate(${mx},${my})`}>
                  <circle r="10" fill="#05080d" stroke="#ff3b5c" />
                  <path d="M-4-4L4 4M4-4L-4 4" stroke="#ff3b5c" strokeWidth="2" />
                </g>
              )}
            </g>
          );
        })}

        {layout.nodes.map((n) => {
          const c = color(n);
          const isSel = n.id === selected;
          const Icon = n.type === "internet" ? Globe : n.type === "network" ? Network : n.you ? Monitor : n.role === "unknown" ? ShieldAlert : n.role === "target" ? Skull : Server;
          const ip = n.ips ? Object.values(n.ips)[0] : n.cidr;
          return (
            <g key={n.id} transform={`translate(${n.x},${n.y})`} className="cursor-pointer" onClick={() => setSelected(isSel ? null : n.id)}>
              {n.type === "network" ? (
                <polygon points="0,-30 26,-15 26,15 0,30 -26,15 -26,-15" fill="#05080d" stroke={c} strokeWidth={isSel ? 3 : 2} filter="url(#glow)" />
              ) : (
                <rect x={-26} y={-26} width={52} height={52} rx={n.type === "internet" ? 26 : 10} fill="#05080d" stroke={c} strokeWidth={isSel ? 3 : 2} filter="url(#glow)" />
              )}
              {n.type === "host" && n.status === "RUNNING" && (
                <circle cx={20} cy={-20} r={4} fill="#00ff9c">
                  <animate attributeName="opacity" values="1;.3;1" dur="1.4s" repeatCount="indefinite" />
                </circle>
              )}
              <foreignObject x={-11} y={-11} width={22} height={22} style={{ color: c }}>
                <Icon size={22} />
              </foreignObject>
              <text y={44} textAnchor="middle" className="font-mono" fontSize="13" fill="#e2e8f0">{n.label}</text>
              {ip && <text y={60} textAnchor="middle" className="font-mono" fontSize="11" fill={c}>{ip}</text>}
              {n.ports && n.ports.length > 0 && (
                <g transform="translate(26,-30)">
                  <rect width={28} height={16} rx={4} fill="#0e1726" stroke={c} strokeOpacity=".7" />
                  <text x={14} y={12} textAnchor="middle" fontSize="10" fill={c} className="font-mono">{n.ports.length}p</text>
                </g>
              )}
            </g>
          );
        })}
      </svg>

      <div className="absolute bottom-3 left-3 flex flex-wrap gap-3 text-[11px] font-mono bg-void/80 border border-edge rounded-md px-3 py-1.5">
        <span className="text-neon">■ {t("labs.legendYou")}</span>
        <span className="text-threat">■ {t("labs.legendTarget")}</span>
        <span className="text-warn">■ {t("labs.legendUnknown")}</span>
        <span className="text-cyber">⬢ {t("labs.topology")}</span>
        <span className="text-muted">{data?.discovered_hosts ?? 0} {t("labs.discovered")}</span>
      </div>

      {sel && sel.type === "host" && (
        <div className="absolute top-3 right-3 w-72 panel p-4 text-sm shadow-cyber">
          <div className="flex items-center justify-between">
            <div className="font-mono text-slate-100">{sel.label}</div>
            <button className="text-muted hover:text-slate-200" onClick={() => setSelected(null)}>✕</button>
          </div>
          <div className="text-xs font-mono text-muted mt-1 space-y-0.5">
            {Object.entries(sel.ips ?? {}).map(([net, ip]) => (
              <div key={net}><span className="text-cyber">{net}</span> → {ip}</div>
            ))}
            {sel.os && <div>OS: <span className="text-slate-300">{sel.os}</span></div>}
          </div>
          {sel.ports && sel.ports.length > 0 ? (
            <table className="w-full mt-3 text-xs font-mono">
              <tbody>
                {sel.ports.map((p) => (
                  <tr key={`${p.port}/${p.protocol}`} className="border-t border-edge/60">
                    <td className="py-1 text-neon">{p.port}/{p.protocol}</td>
                    <td className="py-1 text-slate-300">{p.service}</td>
                    <td className="py-1 text-muted truncate max-w-[110px]">{[p.product, p.version].filter(Boolean).join(" ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-xs text-muted mt-3 font-mono">— no open ports scanned —</div>
          )}
        </div>
      )}
    </div>
  );
}
