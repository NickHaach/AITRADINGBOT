/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0a0f0d",
        panel: "#121a17",
        line: "rgba(157, 181, 168, 0.12)",
        mist: "#9db5a8",
        signal: "#3dcf91",
        warn: "#e8b84a",
        danger: "#e85d5d",
      },
      fontFamily: {
        display: ["\"IBM Plex Sans\"", "system-ui", "sans-serif"],
        mono: ["\"IBM Plex Mono\"", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
