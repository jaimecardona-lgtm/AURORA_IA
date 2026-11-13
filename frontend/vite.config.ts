import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// En desarrollo, /api se reenvía al backend FastAPI local (mismo origen para el navegador).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
