import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/documents': 'http://127.0.0.1:8001',
      '/spans': 'http://127.0.0.1:8001',
      '/batch': 'http://127.0.0.1:8001',
      '/audit': 'http://127.0.0.1:8001',
      '/entity-queue': 'http://127.0.0.1:8001',
      '/upload': 'http://127.0.0.1:8001',
      '/health': 'http://127.0.0.1:8001',
    },
  },
});
