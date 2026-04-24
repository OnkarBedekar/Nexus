/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Legacy `nexus-*` tokens — remapped to cyberpunk. Keeping these names
        // means existing `text-nexus-textDim` etc. classes across components
        // pick up the new palette without a find-and-replace pass.
        nexus: {
          bg: "#050509", // Void black with blue undertone
          surface: "#0b0b14", // Elevated surface
          surfaceAlt: "#12121f", // Higher elevation / input bg
          border: "#1f1f33", // Subtle borders
          text: "#e4e9f2", // Primary text (slightly warm white)
          textDim: "#6b7286", // Secondary / muted text
          // Entity types remap — keep semantic names, upgrade to neon hex.
          company: "#00ff88", // Acid green
          person: "#ff00ff", // Hot magenta
          concept: "#ffaa00", // Amber
          claim: "#00d4ff", // Electric cyan (primary)
          paper: "#b57bff", // Neon violet
        },
        // Semantic layer new components can target without hardcoding hex.
        cyber: {
          void: "#050509",
          panel: "#0b0b14",
          panelAlt: "#12121f",
          border: "#1f1f33",
          borderBright: "#2a2a4a",
          text: "#e4e9f2",
          textDim: "#6b7286",
          accent: "#00d4ff", // PRIMARY - electric cyan
          accentSoft: "#00d4ff20",
          secondary: "#ff00ff", // Hot magenta (CTAs, hero flourish)
          tertiary: "#00ff88", // Acid green (success, confidence, active state)
          warn: "#ffaa00", // Amber
          danger: "#ff3366", // Error pink-red
        },
      },
      fontFamily: {
        display: [
          '"Orbitron"',
          '"Share Tech Mono"',
          "ui-monospace",
          "monospace",
        ],
        mono: [
          '"JetBrains Mono"',
          '"Fira Code"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
        hud: ['"Share Tech Mono"', '"JetBrains Mono"', "monospace"],
      },
      boxShadow: {
        // Stacked box-shadows create the "neon sign" effect. Outer shadow has
        // low alpha + wide blur; inner shadow has high alpha + tight blur.
        "neon-cyan":
          "0 0 4px #00d4ff, 0 0 12px rgba(0, 212, 255, 0.4)",
        "neon-cyan-lg":
          "0 0 8px #00d4ff, 0 0 24px rgba(0, 212, 255, 0.5), 0 0 48px rgba(0, 212, 255, 0.25)",
        "neon-magenta":
          "0 0 4px #ff00ff, 0 0 12px rgba(255, 0, 255, 0.45)",
        "neon-green":
          "0 0 4px #00ff88, 0 0 12px rgba(0, 255, 136, 0.4)",
        "neon-pink":
          "0 0 4px #ff3366, 0 0 12px rgba(255, 51, 102, 0.4)",
        "hud-inset":
          "inset 0 1px 0 rgba(0, 212, 255, 0.1), inset 0 -1px 0 rgba(0, 212, 255, 0.05)",
      },
      dropShadow: {
        "neon-cyan": "0 0 6px rgba(0, 212, 255, 0.75)",
        "neon-magenta": "0 0 6px rgba(255, 0, 255, 0.75)",
        "neon-green": "0 0 6px rgba(0, 255, 136, 0.75)",
      },
      keyframes: {
        // Legacy — kept for existing components still using them.
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(0, 212, 255, 0.6)" },
          "70%": { boxShadow: "0 0 0 10px rgba(0, 212, 255, 0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(0, 212, 255, 0)" },
        },
        "slide-in-bottom": {
          "0%": { transform: "translateY(8px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "slide-in-right": {
          "0%": { transform: "translateX(16px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        // Cyberpunk.
        blink: {
          "0%, 50%": { opacity: "1" },
          "50.01%, 100%": { opacity: "0" },
        },
        flicker: {
          "0%, 19%, 21%, 23%, 25%, 54%, 56%, 100%": {
            opacity: "1",
            textShadow:
              "0 0 4px currentColor, 0 0 12px currentColor",
          },
          "20%, 22%, 24%, 55%": {
            opacity: "0.55",
            textShadow: "none",
          },
        },
        "glitch-skew": {
          "0%, 92%, 100%": { transform: "translate(0) skew(0)" },
          "93%": { transform: "translate(-2px, 1px) skew(-1deg)" },
          "95%": { transform: "translate(2px, -1px) skew(1deg)" },
          "97%": { transform: "translate(-1px, 2px) skew(-0.5deg)" },
          "99%": { transform: "translate(1px, 0) skew(0.5deg)" },
        },
        "rgb-shift": {
          "0%, 100%": {
            textShadow: "-1px 0 #ff00ff, 1px 0 #00d4ff",
          },
          "50%": {
            textShadow: "1px 0 #ff00ff, -1px 0 #00d4ff",
          },
        },
        scanline: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        "hud-pulse": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.65", transform: "scale(0.96)" },
        },
        "gradient-shift": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
      },
      animation: {
        "pulse-ring": "pulse-ring 1.6s infinite",
        "slide-in-bottom": "slide-in-bottom 220ms ease-out",
        "slide-in-right": "slide-in-right 200ms ease-out",
        blink: "blink 1s steps(2, end) infinite",
        flicker: "flicker 5s infinite",
        "glitch-skew": "glitch-skew 7s infinite",
        "rgb-shift": "rgb-shift 2.5s ease-in-out infinite",
        scanline: "scanline 8s linear infinite",
        "hud-pulse": "hud-pulse 2s ease-in-out infinite",
        "gradient-shift": "gradient-shift 4s ease infinite",
      },
      backgroundImage: {
        // Subtle tech grid — 1px accent lines on 50px grid.
        "cyber-grid":
          "linear-gradient(rgba(0, 212, 255, 0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 212, 255, 0.04) 1px, transparent 1px)",
        // CRT scanlines — 2px dark, 2px transparent, repeated.
        scanlines:
          "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 0, 0, 0.35) 2px, rgba(0, 0, 0, 0.35) 3px)",
      },
      backgroundSize: {
        grid: "50px 50px",
      },
    },
  },
  plugins: [],
};
