import type { Config } from "tailwindcss"

const config: Config = {

  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}"
  ],

  theme: {

    extend: {

      colors: {

        background: "#0b0f14",

        panel: "#111827",

        border: "#1f2937",

        text: "#e5e7eb",

        muted: "#94a3b8",

        viridis: {
          50: "#440154",
          100: "#482777",
          200: "#3E4989",
          300: "#31688E",
          400: "#26828E",
          500: "#1F9E89",
          600: "#35B779",
          700: "#6CCE59",
          800: "#B4DE2C",
          900: "#FDE725"
        }
      },

      fontFamily: {
        mono: [
          "JetBrains Mono",
          "Fira Code",
          "monospace"
        ]
      },

      boxShadow: {
        panel:
          "0 0 0 1px #1f2937"
      }
    }
  },

  plugins: []
}

export default config
