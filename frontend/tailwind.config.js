/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#0e0e0c',
          900: '#15141f'.replace('15141f', '141311'),
          850: '#1a1916',
          800: '#211f1b',
          700: '#2a2823',
          600: '#3a3731',
          500: '#6b6862',
          400: '#9a968d',
          300: '#c8c4ba',
          200: '#e8e6e1',
          100: '#f5f3ee'
        },
        frog: {
          DEFAULT: '#d97706',
          soft: '#b46306',
          glow: '#f59e0b'
        },
        moss: '#5b8c5a',
        rust: '#a4421b'
      },
      fontFamily: {
        display: ['"Fraunces"', 'Georgia', 'serif'],
        body: ['"Geist"', 'system-ui', 'sans-serif'],
        mono: ['"Geist Mono"', 'ui-monospace', 'monospace']
      },
      letterSpacing: {
        tightest: '-0.04em'
      }
    }
  },
  plugins: []
};
