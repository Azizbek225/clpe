import { useTranslation } from "react-i18next";
import { Trophy } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { useAuth } from "../hooks/useAuth";
import { PageHeader } from "../components/ui";

export default function Leaderboard() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { data: global } = useApi<any[]>("/leaderboard?limit=50");
  const { data: ctf } = useApi<any[]>("/ctf/leaderboard");
  const medal = (r: number) => ["🥇", "🥈", "🥉"][r - 1] ?? `#${r}`;
  const Table = ({ rows, value, unit }: { rows: any[]; value: string; unit: string }) => (
    <table className="w-full text-sm font-mono">
      <tbody>
        {rows.map((r) => (
          <tr key={r.username} className={`border-t border-edge ${r.username === user?.username ? "bg-neon/5 text-neon" : ""}`}>
            <td className="py-2.5 px-3 w-14">{medal(r.rank)}</td>
            <td className="py-2.5">{r.username}</td>
            {r.level !== undefined && <td className="py-2.5 text-muted">LVL {r.level}</td>}
            <td className="py-2.5 px-3 text-right text-warn">{r[value]} {unit}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
  return (
    <div>
      <PageHeader title={t("board.title")} icon={<Trophy />} />
      <div className="grid lg:grid-cols-2 gap-6">
        <section className="panel p-4"><h2 className="font-mono text-cyber mb-2 px-3">{t("board.global")}</h2><Table rows={global ?? []} value="xp" unit="XP" /></section>
        <section className="panel p-4"><h2 className="font-mono text-cyber mb-2 px-3">{t("board.ctf")}</h2><Table rows={ctf ?? []} value="points" unit="pts" /></section>
      </div>
    </div>
  );
}
