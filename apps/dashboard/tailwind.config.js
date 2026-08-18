/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#070b10",
        panel: "#101820",
        line: "rgba(148, 174, 196, 0.12)",
        mist: "#9aadb8",
        ivory: "#e8eef3",
        signal: "#6eb8c9",
        gain: "#5cbf9a",
        warn: "#d4a05a",
        danger: "#d47878",
      },
      fontFamily: {
        display: ["\"Syne\"", "system-ui", "sans-serif"],
        sans: ["\"DM Sans\"", "system-ui", "sans-serif"],
        mono: ["\"JetBrains Mono\"", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
