import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0A0A0A",
        surface: "#111111",
        card: "#1A1A1A",
        border: "#222222",
        "border-focus": "#2A2A2A",
        accent: "#2563EB", // Electric blue single accent
        foreground: "#FFFFFF",
        secondary: "#E5E5E5",
        muted: "#737373",
        "muted-hover": "#A3A3A3",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "sans-serif"],
        mono: ["var(--font-geist-mono)", "monospace"],
      },
      borderRadius: {
        sm: "2px",
        DEFAULT: "2px",
        md: "4px",
        lg: "8px",
      },
    },
  },
  plugins: [],
};
export default config;
