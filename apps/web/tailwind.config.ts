import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        brand: {
          bg:           '#f4f8fb',
          surface:      '#ffffff',
          border:       '#d8e0ea',
          ink:          '#14212b',
          muted:        '#5f7184',
          faint:        '#8496a9',
          accent:       '#1e4f85',
          'accent-soft':'#eaf3ff',
        },
        tone: {
          neutral:  '#8496a9',
          active:   '#1e4f85',
          retrying: '#d08a1f',
          success:  '#2f855a',
          danger:   '#c74b4b',
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', '"Segoe UI"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: {
        card:  '1rem',
        pill:  '999px',
        badge: '0.65rem',
      },
    },
  },
  plugins: [],
};

export default config;
