/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#05080d",
        panel: "#0a111c",
        panel2: "#0e1726",
        edge: "#1a2a3d",
        neon: { DEFAULT: "#00ff9c", dim: "#00c77a" },
        cyber: { DEFAULT: "#22d3ee", dim: "#0e7490" },
        threat: "#ff3b5c",
        warn: "#ffb020",
        violet: "#a78bfa",
        muted: "#7d8ea3",
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "'Fira Code'", "ui-monospace", "Consolas", "monospace"],
        sans: ["Inter", "'Segoe UI'", "system-ui", "sans-serif"],
      },
      boxShadow: {
        neon: "0 0 0 1px rgba(0,255,156,.35), 0 0 18px rgba(0,255,156,.15)",
        cyber: "0 0 0 1px rgba(34,211,238,.35), 0 0 18px rgba(34,211,238,.15)",
        threat: "0 0 0 1px rgba(255,59,92,.4), 0 0 18px rgba(255,59,92,.15)",
      },
      keyframes: {
        pulseDot: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".35" } },
        scan: { "0%": { transform: "translateY(-100%)" }, "100%": { transform: "translateY(100%)" } },
      },
      animation: { pulseDot: "pulseDot 1.4s ease-in-out infinite", scan: "scan 3s linear infinite" },
    },
  },
  plugins: [],
};
