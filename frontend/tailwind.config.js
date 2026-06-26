/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#efe5d2",
          100: "#d6ad68",
          500: "#c28d39",
          600: "#710912",
          700: "#362822",
          900: "#0d0d0d",
        },
      },
    },
  },
  plugins: [],
};
