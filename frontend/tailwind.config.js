/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f7f6f2",
        ink: "#252923",
        olive: "#66704e",
        gold: "#b89a5d",
        line: "#e9e7df",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Manrope", "Inter", "ui-sans-serif", "sans-serif"],
      },
      boxShadow: {
        card: "0 2px 14px rgba(48, 47, 39, 0.035)",
      },
    },
  },
  plugins: [],
};
