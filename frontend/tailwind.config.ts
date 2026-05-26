import type { Config } from "tailwindcss";

// Design tokens locked to PRD Section 8.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg:       "#0a0a0a",
        surface:  "#1a1a1a",
        border:   "#2a2a2a",
        text:     "#f5f5f5",
        muted:    "#a3a3a3",
        accent:   "#34E9F7",
        success:  "#22c55e",
        warning:  "#f59e0b",
        danger:   "#ef4444",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
