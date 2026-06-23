/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#fff3d5",
          100: "#ffe2a0",
          500: "#f3c760",
          600: "#c99531",
          700: "#9f2335",
          900: "#19080f",
        },
      },
    },
  },
  plugins: [],
};
