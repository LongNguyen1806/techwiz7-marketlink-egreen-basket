import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const BACKEND_URL = 'http://localhost:8000';

// Dev proxy: /api, /media (HTTP) and /ws (WebSocket) are forwarded to the Django backend,
// so the frontend only ever uses same-origin relative URLs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': { target: BACKEND_URL, changeOrigin: true },
      '/media': { target: BACKEND_URL, changeOrigin: true },
      '/ws': {
        target: BACKEND_URL,
        ws: true,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            // Sockets dropped on page reload or backend restart are expected noise.
            if (err.code === 'ECONNRESET' || err.code === 'ECONNABORTED') return;
            console.warn('[Vite WS Proxy Warning]', err.message);
          });
        },
      },
    },
  },
});
