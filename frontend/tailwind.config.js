/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          50: "#FAF8F5",
          100: "#F5EFEB",
          200: "#EFE9DF",
          300: "#DCD3C7",
          400: "#C8BEB0",
          500: "#AFA495",
          600: "#8C8275",
          700: "#6C645C",
          800: "#4A453E",
          900: "#2B2724",
        },
        ink: {
          DEFAULT: "#181615",
          black: "#110F0E",
          pure: "#121212",
          muted: "#5C554E",
          light: "#7A7268",
        },
        crimson: {
          DEFAULT: "#8C2524",
          hover: "#A32B2A",
          dark: "#6E1D1C",
        },
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "system-ui", "-apple-system", "sans-serif"],
        serif: ["Playfair Display", "Georgia", "serif"],
        "editorial-masthead": ["Cinzel", "Playfair Display", "Georgia", "serif"],
        "editorial-heading": ["Playfair Display", "Georgia", "Times New Roman", "serif"],
        "editorial-body": ["Newsreader", "Georgia", "Times New Roman", "serif"],
      },
    },
  },
  plugins: [],
};
