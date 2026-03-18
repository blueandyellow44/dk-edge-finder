/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0f1117',
        card: '#1a1d27',
        border: '#2a2d3a',
        muted: '#9ca3af',
        accent: '#8b5cf6',
        primary: '#e4e4e7',
        'dk-green': '#22c55e',
        'dk-yellow': '#eab308',
        'dk-orange': '#f97316',
        'dk-red': '#ef4444',
        'dk-blue': '#3b82f6',
      },
      fontFamily: {
        mono: ["'SF Mono'", "'Fira Code'", 'monospace'],
      },
    },
  },
  plugins: [],
}
