import { useEffect, useRef } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { getAccessToken, wsUrl } from "../api/client";

/** Lab mashinasi ichidagi shell (WebSocket orqali). Host tizimiga kirish yo'q. */
export default function Terminal({ machineId }: { machineId: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const term = new XTerm({
      cursorBlink: true,
      fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
      fontSize: 13,
      theme: { background: "#05080d", foreground: "#d1fae5", cursor: "#00ff9c", green: "#00ff9c", cyan: "#22d3ee", red: "#ff3b5c", selectionBackground: "#00ff9c44" },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(ref.current!);
    fit.fit();
    term.writeln("\x1b[32m[CLPE]\x1b[0m lab konsoliga ulanmoqda…");

    const ws = new WebSocket(wsUrl(`/ws/console/${machineId}?token=${encodeURIComponent(getAccessToken() ?? "")}`));
    ws.binaryType = "arraybuffer";
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "resize", rows: term.rows, cols: term.cols }));
      term.focus();
    };
    ws.onmessage = (e) => term.write(typeof e.data === "string" ? e.data : new Uint8Array(e.data));
    ws.onclose = (e) => term.writeln(`\r\n\x1b[31m[CLPE] ulanish yopildi (${e.code})\x1b[0m`);
    const sub = term.onData((d) => ws.readyState === 1 && ws.send(JSON.stringify({ type: "input", data: d })));
    const onResize = () => {
      fit.fit();
      if (ws.readyState === 1) ws.send(JSON.stringify({ type: "resize", rows: term.rows, cols: term.cols }));
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      sub.dispose();
      ws.close();
      term.dispose();
    };
  }, [machineId]);

  return <div ref={ref} className="h-[420px] w-full rounded-lg border border-edge bg-void p-2" />;
}
