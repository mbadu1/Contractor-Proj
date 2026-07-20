/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#07090d",
          900: "#0c1017",
          850: "#111722",
          800: "#161d2b",
          700: "#1e2738",
          600: "#2a3548",
        },
        mist: {
          100: "#e8edf5",
          200: "#c5cedd",
          300: "#8b97ab",
          400: "#6b778c",
        },
        accent: {
          DEFAULT: "#3d9cf0",
          dim: "#2a6fad",
          glow: "#5eb0ff",
        },
        good: "#3ecf8e",
        warn: "#e8a838",
        bad: "#e85d5d",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
