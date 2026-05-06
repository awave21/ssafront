/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: {
          0: '#050508',
          1: '#09090f',
          2: '#0e0e17',
          3: '#131320',
          4: '#1a1a2a',
          5: '#20202e',
        },
        border: {
          DEFAULT: '#181826',
          bright: '#22223a',
        },
        acid: '#c8f752',
        muted: '#4a4a62',
        dim: '#2a2a3e',
      },
      fontFamily: {
        sans:    ['Manrope', 'system-ui', 'sans-serif'],
        mono:    ['JetBrains Mono', 'ui-monospace', 'monospace'],
        display: ['Syne', 'system-ui', 'sans-serif'],
      },
      animation: {
        blink:    'blink 1.2s step-end infinite',
        'slide-up': 'slideUp 0.18s ease-out both',
        'fade-in':  'fadeIn 0.2s ease-out both',
        'pulse-dot': 'pulseDot 1.4s ease-in-out infinite',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        pulseDot: {
          '0%, 80%, 100%': { transform: 'scale(0.6)', opacity: '0.4' },
          '40%':           { transform: 'scale(1)',   opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
