/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'DM Sans'", "system-ui", "sans-serif"],
      },
      colors: {
        navy: {
          900: "#0F172A",
          800: "#1E293B",
          700: "#334155",
        },
        brand: {
          green: "#059669",
          red: "#DC2626",
          amber: "#D97706",
          blue: "#2563EB",
        },
      },
    },
  },
  plugins: [],
};
