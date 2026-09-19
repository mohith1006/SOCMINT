/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // India-flag-inspired accent, used sparingly for a "sovereign platform" feel
        saffron: "#FF9933",
        indiagreen: "#138808",
      },
    },
  },
  plugins: [],
};
