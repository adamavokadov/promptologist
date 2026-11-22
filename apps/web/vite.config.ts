import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  root: import.meta.dirname,
  plugins: [react()],
  build: { outDir: path.resolve(import.meta.dirname, '../../dist/public'), emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 900 },
  server: { port: 5173, proxy: { '/api': 'http://localhost:3000', '/healthz': 'http://localhost:3000' } },
});
