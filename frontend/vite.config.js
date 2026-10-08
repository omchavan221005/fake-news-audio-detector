import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'
import tailwindcss from 'tailwindcss'
import autoprefixer from 'autoprefixer'

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const tailwindConfigPath = path.resolve(__dirname, 'tailwind.config.js');

export default defineConfig({
  root: __dirname,
  plugins: [react()],
  css: {
    postcss: {
      plugins: [
        tailwindcss({ config: tailwindConfigPath }),
        autoprefixer(),
      ],
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
