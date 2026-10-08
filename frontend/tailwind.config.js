import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const toGlob = (rel) => path.resolve(__dirname, rel).split(path.sep).join('/');

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    toGlob('./index.html'),
    toGlob('./src/**/*.{js,ts,jsx,tsx}'),
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#080b11',
          800: '#0f1523',
          700: '#162035',
          600: '#1e293b',
        },
      },
    },
  },
  plugins: [],
}
