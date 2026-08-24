/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#090d16',
        surface: '#111827',
        'surface-light': '#1e293b',
        'surface-border': '#334155',
        primary: '#38bdf8',
        bullish: '#10b981',
        bearish: '#ef4444',
        neutral: '#f59e0b',
      },
    },
  },
  plugins: [],
}
